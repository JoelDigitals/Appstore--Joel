# in z.B. yourapp/context_processors.py

from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        user_notifications = Notification.objects.filter(user=request.user, read=False)
    else:
        user_notifications = []
    return {
        'user_notifications': user_notifications,
    }
