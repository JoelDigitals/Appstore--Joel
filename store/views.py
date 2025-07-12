from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from .models import App, Version, PushSubscription, Developer, VersionDownload, CATEGORY_CHOICES, Notification
from .forms import AppWithVersionForm, VersionForm, DeveloperForm, AppEditForm
from .tasks import start_background_check, start_background_check_version
from django.http import FileResponse, JsonResponse, HttpResponse, FileResponse, HttpResponseNotFound, HttpResponseForbidden
import json
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from kombu.exceptions import OperationalError as KombuOpError
from celery import Celery
import os
import zipfile
from io import BytesIO
from django.utils import timezone
from django.db.models import F
from django.db.models import Count
from datetime import timedelta
from django.db.models import Q
from .utils import send_push_notification_to_admins
from django.utils.crypto import get_random_string
from django.core.cache import cache

app_celery = Celery()

from django.http import JsonResponse

def get_notifications_for_user(user):
    notification_count = cache.get(f'notification_count_{user.id}')
    if notification_count is None:
        notification_count = Notification.objects.filter(user=user, read=False).count()
        cache.set(f'notification_count_{user.id}', notification_count, timeout=60*5)  # Cache für 5 Minuten
    return Notification.objects.filter(
        Q(user=user),
        read=False
    ).order_by('-created_at')




@login_required
def notifications_check(request):
    user = request.user
    notifications_qs = Notification.objects.filter(user=user, is_read=False).order_by('-created_at')[:10]
    notifications = list(notifications_qs.values('id', 'message', 'created_at'))
    count = len(notifications)
    for n in notifications:
        n['created_at'] = n['created_at'].strftime("%d.%m.%Y %H:%M")
    return JsonResponse({
        "count": count,
        "notifications": notifications,
    })

@login_required
@csrf_exempt
def push_subscribe(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        if not endpoint:
            return JsonResponse({'error': 'No endpoint'}, status=400)

        # Existierende Subscriptions löschen, falls mehrfach vorhanden
        PushSubscription.objects.filter(endpoint=endpoint).delete()

        # Neue Subscription speichern
        PushSubscription.objects.create(
            user=request.user,
            endpoint=endpoint,
            data=data
        )
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@staff_member_required
def download_all_media(request):
    # Verzeichnis mit den Medien-Dateien
    media_root = settings.MEDIA_ROOT

    # Temporärer Speicher im RAM für ZIP-Datei
    zip_buffer = BytesIO()

    # ZIP-Datei erstellen
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(media_root):
            for file in files:
                full_path = os.path.join(root, file)
                # Relativer Pfad innerhalb der ZIP-Datei
                relative_path = os.path.relpath(full_path, media_root)
                zip_file.write(full_path, arcname=relative_path)

    # ZIP-Puffer an den Anfang zurücksetzen
    zip_buffer.seek(0)

    # Antwort mit ZIP als Download
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="media_files.zip"'
    return response


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registrierung erfolgreich! Du bist nun eingeloggt.')
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'store/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'store/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')
    
@login_required
def create_app_view(request):
    developer = request.user.developer
    if request.method == 'POST':
        form = AppWithVersionForm(request.POST, files=request.FILES)
        if form.is_valid():
            app = form.save(developer=developer)
            version = form.save_version(app)
            # Screenshots werden schon in form.save() gespeichert, kein doppeltes Speichern hier!

            return redirect('version_app_status_view', version_id=version.id)
    else:
        form = AppWithVersionForm()

    return render(request, 'store/create_app.html', {'form': form})


def version_status_app_view(request, version_id):
    version = get_object_or_404(Version, id=version_id)

    # Starte die Prüfung nur, wenn sie noch nicht läuft oder nicht abgeschlossen ist
    if version.checking_status not in ['running', 'passed']:
        try:
            start_background_check(version.id)
            messages.success(request, 'Die Prüfung läuft im Hintergrund.')

            send_push_notification_to_admins(
                title="Neue App-Prüfung gestartet",
                body=f"Die Version {version.version_number} von {version.app.name} wird geprüft.",
                url=f"/store/version/{version.id}/"
            )
        except KombuOpError:
            messages.warning(request,
                'Die Prüfung konnte nicht gestartet werden.')

    # Rendern einer Status-Seite mit den Infos zur Version und Prüfung
    return render(request, 'store/version_status.html', {'version': version})

def version_status_view(request, version_id):
    version = get_object_or_404(Version, id=version_id)

    # Starte die Prüfung nur, wenn sie noch nicht läuft oder nicht abgeschlossen ist
    if version.checking_status not in ['running', 'passed']:
        try:
            start_background_check_version(version.id)
            messages.success(request, 'Die Prüfung läuft im Hintergrund.')
        except KombuOpError:
            messages.warning(request,
                'Die Prüfung konnte nicht gestartet werden.')

    # Rendern einer Status-Seite mit den Infos zur Version und Prüfung
    return render(request, 'store/version_status.html', {'version': version})


@login_required
def version_status_api(request, version_id):
    version = get_object_or_404(Version, id=version_id, app__owner=request.user)
    return JsonResponse({'status': version.checking_status})

@login_required
def developer_dashboard(request):
    try:
        developer = Developer.objects.get(user=request.user)
    except Developer.DoesNotExist:
        return redirect('create_developer')  # Developer-Profil erstellen, falls noch nicht vorhanden

    query = request.GET.get("q", "")
    apps = App.objects.filter(developer=developer).order_by('-created_at')

    if query:
        apps = apps.filter(name__icontains=query)

    apps_with_latest = []
    for app in apps:
        latest_version = app.versions.order_by('-uploaded_at').first()
        apps_with_latest.append({
            'app': app,
            'latest_version': latest_version
        })

    return render(request, 'store/developer_dashboard.html', {
        'developer': developer,
        'apps_with_latest': apps_with_latest,
        'query': query
    })

@login_required
def edit_developer_view(request, developer_id):
    developer = get_object_or_404(Developer, id=developer_id, user=request.user)

    if request.method == 'POST':
        form = DeveloperForm(request.POST, request.FILES, instance=developer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Entwicklerprofil erfolgreich aktualisiert.')
            return redirect('developer_dashboard')
    else:
        form = DeveloperForm(instance=developer)

    return render(request, 'store/edit_developer.html', {'form': form, 'developer': developer})

@login_required
def delete_developer_view(request, developer_id):
    developer = get_object_or_404(Developer, id=developer_id, user=request.user)

    if request.method == 'POST':
        # Alle Apps des Entwicklers löschen
        developer.apps.all().delete()
        developer.delete()
        messages.success(request, 'Entwicklerprofil erfolgreich gelöscht.')
        return redirect('home')

    return render(request, 'store/delete_developer.html', {'developer': developer})

@login_required
def app_detail_dev_view(request, app_id):
    app = get_object_or_404(App, id=app_id, developer=request.user.developer)
    versions = app.versions.order_by('-uploaded_at')  # Alle Versionen laden

    return render(request, 'store/app_detail_dev.html', {
        'app': app,
        'versions': versions,
    })

@login_required
def edit_app_view(request, app_id):
    app = get_object_or_404(App, id=app_id, developer=request.user.developer)

    if request.method == 'POST':
        form = AppEditForm(request.POST, request.FILES, instance=app)
        if form.is_valid():
            form.save()
            messages.success(request, 'App erfolgreich aktualisiert.')
            return redirect('developer_dashboard')
    else:
        form = AppEditForm(instance=app)

    return render(request, 'store/edit_app.html', {'form': form, 'app': app})

@login_required
def delete_app_view(request, app_id):
    app = get_object_or_404(App, id=app_id, developer=request.user.developer)
    
    if request.method == 'POST':
        app.delete()
        messages.success(request, 'App erfolgreich gelöscht.')
        return redirect('developer_dashboard')

    return render(request, 'store/delete_app.html', {'app': app})

@login_required
def app_screenshots_view(request, app_id):
    app = get_object_or_404(App, id=app_id, developer=request.user.developer)
    screenshots = app.screenshots.all()

    return render(request, 'store/app_screenshots.html', {
        'app': app,
        'screenshots': screenshots,
    })

@login_required
def upload_screenshots_view(request, app_id):
    app = get_object_or_404(App, id=app_id, developer=request.user.developer)

    if request.method == 'POST':
        files = request.FILES.getlist('screenshots')
        if files:
            for file in files:
                app.screenshots.create(image=file)
            messages.success(request, 'Screenshots erfolgreich hochgeladen.')
            return redirect('app_screenshots', app_id=app.id)
        else:
            messages.error(request, 'Bitte mindestens ein Screenshot hochladen.')

    return render(request, 'store/upload_screenshots.html', {'app': app})

@login_required
def create_developer_view(request):

    if request.method == 'POST':
        form = DeveloperForm(request.POST)
        if form.is_valid():
            developer = form.save(commit=False)
            developer.user = request.user
            developer.save()
            return redirect('developer_dashboard')
    else:
        form = DeveloperForm()

    return render(request, 'store/create_developer.html', {'form': form})

def home(request):
    query = request.GET.get('q', '')
    user = request.user

    if user.is_authenticated:
        notifications = Notification.objects.filter(
            Q(user=user),  # Benachrichtigungen für diesen Nutzer 
            read=False  # Nur ungelesene Benachrichtigungen
        ).order_by('-created_at')
        notifications_count = notifications.count()
    else:
        notifications = Notification.objects.filter(
            user__isnull=True,  # Benachrichtigungen für alle Nutzer
            read=False  # Nur ungelesene Benachrichtigungen
        ).order_by('-created_at')

    # Alle veröffentlichten Apps
    all_apps = App.objects.filter(
        published=True,
        published_at__lte=timezone.now()
    )

    if query:
        all_apps = all_apps.filter(name__icontains=query)

    # Top Downloads
    top_downloads = all_apps.order_by('-download_count')[:10]

    # Trending Apps (letzte 7 Tage)
    seven_days_ago = timezone.now() - timedelta(days=7)
    trending_apps_ids = VersionDownload.objects.filter(
        downloaded_at__gte=seven_days_ago,
        version__app__in=all_apps
    ).values('version__app').annotate(
        downloads_last_week=Count('id')
    ).order_by('-downloads_last_week').values_list('version__app', flat=True)[:10]
    trending_apps = App.objects.filter(id__in=trending_apps_ids)

    # --- Empfehlungen für eingeloggte Nutzer ---
    recommended_apps = []
    if user.is_authenticated:
        # Finde die zuletzt genutzten Apps des Users
        last_downloads = VersionDownload.objects.filter(
            user=user
        ).order_by('-downloaded_at')[:5]

        # Extrahiere Plattform/Kategorie-Präferenzen
        preferred_platforms = set()
        preferred_categories = set()
        for download in last_downloads:
            app = download.version.app
            preferred_platforms.add(app.platform)
            preferred_categories.add(app.category)

        # Finde empfohlene Apps basierend auf diesen Präferenzen
        recommended_apps = App.objects.filter(
            published=True,
            published_at__lte=timezone.now(),
            platform__in=preferred_platforms,
            category__in=preferred_categories
        ).exclude(
            versions__versiondownload__user=user
        ).distinct().order_by('-download_count')[:6]

    context = {
        'query': query,
        'all_apps': all_apps,
        'top_downloads': top_downloads,
        'trending_apps': trending_apps,
        'recommended_apps': recommended_apps,
        'notifications': notifications,
        'notifications_count': notifications_count,
    }
    return render(request, 'store/home.html', context)


def platform_view(request, platform_name):
    query = request.GET.get('q', '')
    apps = App.objects.filter(
        platform__iexact=platform_name,
        published=True,
        published_at__lte=timezone.now()  # Vergangenheit oder jetzt
    )
    if query:
        apps = apps.filter(name__icontains=query)
    context = {'apps': apps, 'platform': platform_name, 'query': query}
    return render(request, 'store/platform.html', context)

@login_required
def notifications_view(request):
    user = request.user
    notifications = Notification.objects.filter(
        Q(user=user) | Q(user__isnull=True)
    ).order_by('-timestamp')
    unread_count = notifications.filter(read=False, user=user).count()

    return render(request, 'store/notifications.html', {
        'notifications': notifications,
        'count': unread_count,
    })

@login_required
def notification_detail(request, pk):
    notification = get_object_or_404(Notification, pk=pk)

    # Falls es eine persönliche Nachricht ist → als gelesen markieren
    if notification.user == request.user and not notification.read:
        notification.read = True
        notification.save()

    return render(request, 'store/notification_detail.html', {
        'notification': notification
    })

@login_required
def mark_all_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, read=False).update(read=True)
    return redirect('notifications')

@login_required
def subscribe_notifications(request):
    if request.method == 'POST':
        endpoint = request.POST.get('endpoint')
        if not endpoint:
            messages.error(request, 'Kein Endpoint angegeben.')
            return redirect('notifications_all')

        # Existierende Subscriptions löschen, falls mehrfach vorhanden
        PushSubscription.objects.filter(endpoint=endpoint).delete()

        # Neue Subscription speichern
        PushSubscription.objects.create(
            user=request.user,
            endpoint=endpoint
        )
        messages.success(request, 'Du hast dich erfolgreich für Benachrichtigungen angemeldet.')
    return redirect('notifications_all')

@login_required
def unsubscribe_notifications(request):
    if request.method == 'POST':
        endpoint = request.POST.get('endpoint')
        if not endpoint:
            messages.error(request, 'Kein Endpoint angegeben.')
            return redirect('notifications_all')

        # Subscription löschen
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        messages.success(request, 'Du hast dich erfolgreich von Benachrichtigungen abgemeldet.')
    return redirect('notifications_all')

def developer_detail_view(request, name):
    # Name ggf. entschlüsseln/entschlacken
    developer = get_object_or_404(Developer, name__iexact=name)
    apps = App.objects.filter(developer=developer, published=True)

    return render(request, 'store/developer_detail.html', {
        'developer': developer,
        'apps': apps,
    })

@login_required
def upload_version(request, app_id):
    app = get_object_or_404(App, id=app_id, developer=request.user.developer)
    if request.method == 'POST':
        form = VersionForm(request.POST, request.FILES)
        if form.is_valid():
            version = form.save(commit=False)
            version.app = app
            version.checking_status = 'pending'
            version.approved = False
            version.save()

            try:
                start_background_check.delay(version.id)
                messages.success(request, 'Neue Version hochgeladen. Prüfung läuft.')
            except KombuOpError:
                messages.warning(request,
                    'Version hochgeladen – konnte Hintergrundprüfung nicht starten (Broker nicht erreichbar).'
                )

            return redirect('version_status', version_id=version.id)
    else:
        form = VersionForm()

    return render(request, 'store/upload_version.html', {'form': form, 'app': app})



def app_detail_view(request, app_id):
    app = get_object_or_404(App, id=app_id, published=True)
    latest_version = app.versions.filter(approved=True).order_by('-uploaded_at').first()

    suggestions = App.objects.filter(
        platform=app.platform,
        published=True,
        published_at__lte=timezone.now()
    ).filter(
        Q(category=app.category) | Q(subcategory=app.subcategory)
    ).exclude(id=app.id).distinct()[:8]

    user_installed_version = None
    if request.user.is_authenticated:
        vd = VersionDownload.objects.filter(
            user=request.user, version__app=app
        ).order_by('-version__uploaded_at').first()
        if vd:
            user_installed_version = vd.version

    return render(request, 'store/app_detail.html', {
        'app': app,
        'latest_version': latest_version,
        'suggestions': suggestions,
        'user_installed_version': user_installed_version,
    })

#Download NEW
@csrf_exempt
@login_required
def get_temporary_download_link(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    data = json.loads(request.body)
    version_id = data.get('version_id')
    version = get_object_or_404(Version, id=version_id, approved=True)
    app = version.app

    token = get_random_string(32)
    cache.set(f"dl_token_{token}", version_id, timeout=60)  # gültig 60 Sekunden

    return JsonResponse({'token': token})

@login_required
def download_file_view(request, token):
    version_id = cache.get(f"dl_token_{token}")
    if not version_id:
        return HttpResponseForbidden("Ungültiger oder abgelaufener Token.")

    version = get_object_or_404(Version, id=version_id, approved=True)

    # Tracking
    VersionDownload.objects.get_or_create(user=request.user, version=version)
    App.objects.filter(id=version.app.id).update(download_count=F('download_count') + 1)

    file_path = version.file.path
    if not os.path.exists(file_path):
        return HttpResponseNotFound("Datei nicht gefunden.")

    response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=os.path.basename(file_path))
    return response

@csrf_exempt
@login_required
def download_start_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    data = json.loads(request.body)
    version_id = data.get('version_id')
    version = get_object_or_404(Version, id=version_id, approved=True)
    app = version.app

    # Zähler + Tracking
    App.objects.filter(id=app.id).update(download_count=F('download_count') + 1)
    VersionDownload.objects.get_or_create(user=request.user, version=version)

    # Für Streaming-Download
    file_path = version.file.path
    total = os.path.getsize(file_path)
    response = FileResponse(open(file_path, 'rb'), content_type='application/octet-stream')
    response['Content-Length'] = total
    response['X-Version-Id'] = str(version_id)
    return response

@csrf_exempt
@login_required
def download_complete(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        version_id = data.get('version_id')
        version = get_object_or_404(Version, id=version_id)
        if version.file and os.path.isfile(version.file.path):
            try:
                os.remove(version.file.path)
            except Exception as e:
                print(f"Fehler beim Löschen der Datei: {e}")
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)








# download old
@login_required
def download_app_view(request, version_id):
    version = get_object_or_404(Version, id=version_id, approved=True)
    
    confirmed = request.session.get(f'download_confirmed_{version_id}', False)
    
    if request.method == 'POST' and not confirmed:
        request.session[f'download_confirmed_{version_id}'] = True
        request.session[f'download_ready_{version_id}'] = True
        return redirect('download_success', version_id=version_id)

    if not confirmed:
        return render(request, 'store/download_confirm.html', {'version': version})
    
    # Wenn schon bestätigt, direkt zur Success-Seite
    return redirect('download_success', version_id=version_id)


@login_required
def download_app_start(request, version_id):
    version = get_object_or_404(Version, id=version_id, approved=True)
    app = version.app

    # Downloadzähler erhöhen
    App.objects.filter(id=app.id).update(download_count=F('download_count') + 1)

    # User-Download-Tracking
    VersionDownload.objects.get_or_create(user=request.user, version=version)

    # User-Agent erkennen
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(mobile_str in user_agent for mobile_str in ['android', 'iphone', 'ipad', 'mobile'])

    if is_mobile:
        context = {'version': version, 'is_mobile': True}
        return render(request, 'store/mobile_download.html', context)
    else:
        return redirect('download_file', version_id=version.id)



@login_required
def download_file_view(request, version_id):
    version = get_object_or_404(Version, id=version_id, approved=True)

    file_path = version.file.path
    filename = os.path.basename(file_path)

    # MIME-Type bestimmen
    if filename.endswith('.apk'):
        content_type = 'application/vnd.android.package-archive'
    elif filename.endswith('.ipa'):
        content_type = 'application/octet-stream'  # IPA hat keinen offiziellen MIME-Type, oft octet-stream
    else:
        content_type = 'application/octet-stream'

    response = FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename=filename,
        content_type=content_type
    )
    return response



@csrf_exempt
@login_required
def download_complete_1(request):
    """
    Wird vom Client nach erfolgreicher Installation aufgerufen.
    Hier kann die APK-Datei gelöscht werden.
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        version_id = data.get('version_id')

        version = get_object_or_404(Version, id=version_id)

        # APK-Datei löschen
        if version.file and os.path.isfile(version.file.path):
            try:
                os.remove(version.file.path)
            except Exception as e:
                print(f"Fehler beim Löschen der APK: {e}")

        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)

@csrf_exempt
def save_push_subscription(request):
    if request.method == "POST" and request.user.is_authenticated:
        data = json.loads(request.body)
        endpoint = data["data"]["endpoint"]
        # Update oder erstellen
        subscription, _ = PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=endpoint,
            defaults={"data": data["data"]}
        )
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error"}, status=400)

@login_required
def my_installed_apps(request):
    # Alle Apps, die der Benutzer installiert hat
    installed_apps = VersionDownload.objects.filter(user=request.user).select_related('app', 'installed_version')

    return render(request, 'apps/my_installed_apps.html', {
        'installed_apps': installed_apps,
    })

def jds_appstore_apps(request):
    apps = App.objects.filter(name="JDS Appstore")
    return render(request, "store/jds_apps.html", {"apps": apps})

@login_required
def developer_list(request):
    developers = Developer.objects.all().order_by('name')
    return render(request, 'store/developer_list.html', {'developers': developers})