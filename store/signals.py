from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Developer

@receiver(post_save, sender=User)
def create_developer_for_user(sender, instance, created, **kwargs):
    if created:
        # Ein eindeutiger Defaultname, z.B. "dev_username"
        default_name = f"dev_{instance.username}"
        # Sicherstellen, dass der Name einmalig ist
        count = 1
        name = default_name
        while Developer.objects.filter(name=name).exists():
            name = f"{default_name}{count}"
            count += 1
        Developer.objects.create(user=instance, name=name)
