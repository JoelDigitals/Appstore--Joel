from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import UserProfile, NotificationSettings

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
def change_password_view(request):  
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        request.user.set_password(new_password)
        request.user.save()
        return redirect('login')
    return render(request, 'settings/change_password.html')

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

