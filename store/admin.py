from django.contrib import admin
from django.contrib import messages
from django.conf import settings
import json
from pywebpush import webpush, WebPushException

from .models import App, AppWarning, Notification, PushSubscription, Version, Developer, AppScreenshot, VersionDownload

# Normale Admin-Registrierungen:
admin.site.register(App)
admin.site.register(AppWarning)
admin.site.register(Version)
admin.site.register(Notification)
admin.site.register(Developer)
admin.site.register(AppScreenshot)
admin.site.register(VersionDownload)

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
