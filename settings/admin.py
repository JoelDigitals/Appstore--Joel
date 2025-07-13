from django.contrib import admin
from .models import UserProfile, NotificationSettings

admin.site.register(NotificationSettings)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'birth_date')
