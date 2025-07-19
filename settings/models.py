from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.html import mark_safe

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    birth_date = models.DateField(blank=True, null=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    social_links = models.JSONField(default=dict, blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"Profil von {self.user.username}"

    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return settings.STATIC_URL + 'avatars/default_avatar.jpg'

class NotificationSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_settings')
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)

    def __str__(self):
        return f"Benachrichtigungseinstellungen für {self.user.username}"
    
class UserSecurity(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security')
    is_deactivated = models.BooleanField(default=False)

    def __str__(self):
        return f"Sicherheitseinstellungen für {self.user.username}"

