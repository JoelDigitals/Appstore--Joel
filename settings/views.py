from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import UserProfile, NotificationSettings, UserSecurity
from django.contrib import messages


@login_required
def user_profile_view(request): 
    profile = request.user.profile
    return render(request, 'settings/user_profile.html', {'profile': profile})  

@login_required
def edit_user_profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        profile.avatar = request.FILES.get('avatar', profile.avatar)
        profile.bio = request.POST.get('bio', profile.bio)
        profile.birth_date = request.POST.get('birth_date', profile.birth_date)
        profile.website = request.POST.get('website', profile.website)
        profile.location = request.POST.get('location', profile.location)
        profile.social_links = request.POST.get('social_links', profile.social_links)
        profile.email = request.POST.get('email', profile.email)
        profile.phone_number = request.POST.get('phone_number', profile.phone_number)
        profile.save()
        return redirect('user_profile')
    return render(request, 'settings/edit_user_profile.html', {'profile': profile})

@login_required
def delete_user_profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        profile.delete()
        return redirect('home')
    return render(request, 'settings/delete_user_profile.html', {'profile': profile})

@login_required
def user_settings_view(request):
    return render(request, 'settings/user_settings.html')

@login_required
def notification_settings_view(request):
    settings = request.user.notification_settings
    if request.method == 'POST':
        settings.email_notifications = request.POST.get('email_notifications') == 'on'
        settings.push_notifications = request.POST.get('push_notifications') == 'on'
        settings.daily_digest = request.POST.get('daily_digest') == 'on'
        settings.save()
        return redirect('user_settings')
    return render(request, 'settings/notification_settings.html', {'settings': settings})


@login_required
def security_settings(request):
    security, _ = UserSecurity.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'deactivate':
            password = request.POST.get('password')
            user = authenticate(username=request.user.username, password=password)
            if user:
                user.is_active = False        # actually disable login
                user.save()
                security.is_deactivated = True
                security.save()
                logout(request)
                messages.success(request, "Dein Konto wurde deaktiviert. Du wirst nun abgemeldet.")
                return redirect('login')
            else:
                messages.error(request, "Falsches Passwort. Konto wurde nicht deaktiviert.")

        elif action == 'delete':
            password = request.POST.get('password')
            user = authenticate(username=request.user.username, password=password)
            if user:
                request.user.delete()
                messages.success(request, "Dein Konto wurde gelöscht.")
                return redirect('home')
            else:
                messages.error(request, "Falsches Passwort. Konto wurde nicht gelöscht.")

    return render(request, 'settings/security_settings.html', {'security': security})