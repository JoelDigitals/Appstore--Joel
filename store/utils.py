# utils.py
from pywebpush import webpush, WebPushException
from django.conf import settings
from .models import PushSubscription
import json

def send_push_notification_to_admins(title, body, url):
    payload = {
        "title": title,
        "body": body,
        "url": url,
    }

    for sub in PushSubscription.objects.filter(user__is_staff=True):
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": "mailto:" + settings.DEFAULT_FROM_EMAIL,
                }
            )
        except WebPushException as ex:
            print(f"WebPush Error: {ex}")
