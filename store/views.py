from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from .models import App, Version, PushSubscription, Developer, VersionDownload, CATEGORY_CHOICES
from .forms import AppWithVersionForm, VersionForm, DeveloperForm, AppEditForm
from .tasks import start_background_check, start_background_check_version
from django.http import FileResponse, JsonResponse, HttpResponse, FileResponse
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

app_celery = Celery()


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

            return redirect('version_status_view', version_id=version.id)
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

@login_required
def home(request):
    query = request.GET.get('q', '')
    user = request.user

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

def app_detail_view(request, app_id):
    app = get_object_or_404(App, id=app_id, published=True)
    latest_version = app.versions.filter(approved=True).order_by('-uploaded_at').first()

    # Vorschläge basierend auf Plattform + Kategorie oder Unterkategorie
    suggestions = App.objects.filter(
        platform=app.platform,
        published=True,
        published_at__lte=timezone.now()
    ).filter(
        Q(category=app.category) | Q(subcategory=app.subcategory)
    ).exclude(id=app.id).distinct()[:8]

    user_installed_version = None
    if request.user.is_authenticated:
        user_downloads = VersionDownload.objects.filter(
            user=request.user,
            version__app=app
        ).order_by('-version__uploaded_at')
        if user_downloads.exists():
            user_installed_version = user_downloads.first().version

    return render(request, 'store/app_detail.html', {
        'app': app,
        'latest_version': latest_version,
        'suggestions': suggestions,
        'user_installed_version': user_installed_version,
        'category': dict(CATEGORY_CHOICES).get(app.category, app.category),  # lesbarer Name
    })

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

            return redirect('version_status')
    else:
        form = VersionForm()

    return render(request, 'store/upload_version.html', {'form': form, 'app': app})

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
def download_success_view(request, version_id):
    version = get_object_or_404(Version, id=version_id)
    # Hier könntest du direkt den Download starten lassen (z.B. per Link/Button)
    return render(request, 'store/download_success.html', {'version': version})

@login_required
def download_file_view(request, version_id):
    # Endpoint zum echten Ausliefern der APK-Datei mit korrektem Content-Type
    version = get_object_or_404(Version, id=version_id, approved=True)
    response = FileResponse(
        version.file.open('rb'),
        as_attachment=True,
        filename=version.file.name,
        content_type='application/vnd.android.package-archive'  # wichtig für APK
    )
    return response

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
def download_complete(request):
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
def save_subscription(request):
    if request.method == "POST":
        data = json.loads(request.body)
        PushSubscription.objects.update_or_create(
            endpoint=data["endpoint"],
            defaults={"data": data}
        )
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "nur POST erlaubt"}, status=405)

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