from django.contrib import admin
from django.contrib import messages
from django.conf import settings
import json
from pywebpush import webpush, WebPushException

from .models import App, AppWarning, Notification, PushSubscription, Version, Developer, AppScreenshot, VersionDownload, AppUpdate, AppInfo, RoadmapItem, EmailVerificationCode

# Normale Admin-Registrierungen:
admin.site.register(App)
admin.site.register(AppWarning)
admin.site.register(Notification)
admin.site.register(Developer)
admin.site.register(AppScreenshot)
admin.site.register(VersionDownload)
admin.site.register(AppInfo)
admin.site.register(AppUpdate)
admin.site.register(RoadmapItem)
admin.site.register(EmailVerificationCode)

# Eigene Admin-Klasse für PushSubscription:
@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("endpoint", "created_at")
    actions = ["send_push"]

    def send_push(self, request, queryset):
        for sub in queryset:
            try:
                webpush(
                    subscription_info=sub.data,
                    data=json.dumps({
                        "title": "Admin-Nachricht",
                        "body": "Ein neues Update ist verfügbar!"
                    }),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_EMAIL}
                )
            except WebPushException as ex:
                self.message_user(request, f"Fehler bei {sub.endpoint[:30]}: {ex}", level=messages.ERROR)
        self.message_user(request, "Benachrichtigungen gesendet.")

@admin.register(Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = ("app", "version_number", "uploaded_at", "checking_status", "approved", "new_version")
    list_filter = ("checking_status", "approved", "new_version")
    search_fields = ("app__name", "version_number")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.checking_status == 'approved':
            return self.readonly_fields + ('checking_log',)
        return self.readonly_fields