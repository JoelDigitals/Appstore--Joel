from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import App, Version, PushSubscription, Developer
from .forms import AppWithVersionForm, VersionForm, DeveloperForm
from django.core.paginator import Paginator
from .tasks import start_background_check
from django.http import FileResponse
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from kombu.exceptions import OperationalError as KombuOpError
from celery import Celery

app_celery = Celery()

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


def version_status_view(request, version_id):
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
def create_developer_view(request):
    if hasattr(request.user, 'developer'):
        return redirect('developer_dashboard')

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
    if query:
        apps = App.objects.filter(name__icontains=query)
    else:
        apps = App.objects.all()
    context = {'apps': apps, 'query': query}
    return render(request, 'store/home.html', context)

def platform_view(request, platform_name):
    query = request.GET.get('q', '')
    apps = App.objects.filter(platform__iexact=platform_name)
    if query:
        apps = apps.filter(name__icontains=query)
    context = {'apps': apps, 'platform': platform_name, 'query': query}
    return render(request, 'store/platform.html', context)

def app_detail_view(request, app_id):
    app = get_object_or_404(App, id=app_id, published=True)
    latest_version = app.versions.filter(approved=True).order_by('-uploaded_at').first()
    return render(request, 'store/app_detail.html', {'app': app, 'latest_version': latest_version})

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

            return redirect('developer_dashboard')
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