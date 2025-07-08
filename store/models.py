from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

# Vordefinierte Altersfreigaben
AGE_RATINGS = [
    ('0', 'Keine Altersbeschränkung'),
    ('6', 'Ab 6 Jahren'),
    ('12', 'Ab 12 Jahren'),
    ('16', 'Ab 16 Jahren'),
    ('18', 'Ab 18 Jahren'),
]

PLATFORM_CHOICES = [
    ('android', 'Android'),
    ('ios', 'iOS'),
    ('windows', 'Windows'),
    ('macos', 'macOS'),
    ('linux', 'Linux'),
]

# Unterstützte Sprachen (ISO Codes + Name)
LANGUAGES = [
    ('de', 'Deutsch'),
    ('en', 'Englisch'),
    ('fr', 'Französisch'),
    # weitere nach Bedarf
]

CHECKING_STATUS = [
    ('pending', 'Ausstehend'),
    ('running', 'In Bearbeitung'),
    ('passed', 'Bestanden'),
    ('failed', 'Fehlgeschlagen'),
]


class Developer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='developer_logos/', blank=True)
    youtube = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    github = models.URLField(blank=True)

    def __str__(self):
        return self.name


def validate_minimum_screenshots(value):
    if value.count() < 3:
        raise ValidationError("Mindestens 3 Screenshots erforderlich.")

class App(models.Model):
    developer = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name='apps')
    name = models.CharField(max_length=255)
    description = models.TextField()
    language = models.CharField(max_length=5, choices=LANGUAGES, default='de')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    age_rating = models.CharField(max_length=2, choices=AGE_RATINGS, default='0')
    icon = models.ImageField(upload_to='app_icons/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.developer.name})"

class AppScreenshot(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name='screenshots')
    image = models.ImageField(upload_to='app_screenshots/')

class Version(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name='versions')
    version_number = models.CharField(max_length=50)
    file = models.FileField(upload_to='app_files/')
    release_notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    checking_status = models.CharField(max_length=10, choices=CHECKING_STATUS, default='pending')
    checking_progress = models.PositiveSmallIntegerField(default=0)
    checking_log = models.TextField(blank=True)  # Protokoll für Prüfungsergebnisse
    approved = models.BooleanField(default=False)  # Ergebnis der Prüfung

    def __str__(self):
        return f"{self.app.name} v{self.version_number}"

# Optional: Warnungen, z.B. Gewalt, Sex, Werbung etc.
WARNING_TYPES = [
    ('violence', 'Gewalt'),
    ('sex', 'Sexuelle Inhalte'),
    ('ads', 'Werbung'),
    ('drugs', 'Drogen'),
    ('none', 'Keine Warnung'),
]

class AppWarning(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name='warnings')
    warning_type = models.CharField(max_length=20, choices=WARNING_TYPES)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.get_warning_type_display()} bei {self.app.name}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # null = an alle
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.title} -> {"Alle" if not self.user else self.user.username}'
    
class PushSubscription(models.Model):
    endpoint = models.TextField(unique=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.endpoint[:40]