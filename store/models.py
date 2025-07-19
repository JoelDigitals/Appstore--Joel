from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

class EmailVerificationCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

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

CATEGORY_CHOICES = [
    ('games', 'Spiele'),
    ('productivity', 'Produktivität'),
    ('education', 'Bildung'),
    ('entertainment', 'Unterhaltung'),
    ('utilities', 'Dienstprogramme'),
    ('social', 'Soziale Netzwerke'),
    ('health', 'Gesundheit'),
    ('lifestyle', 'Lebensstil'),
    ('finance', 'Finanzen'),
    ('travel', 'Reisen'),
    ('news', 'Nachrichten'),
    ('music', 'Musik'),
    ('photo_video', 'Foto & Video'),
    ('books', 'Bücher'),
    ('shopping', 'Einkaufen'),
    ('food_drink', 'Essen & Trinken'),
    ('sports', 'Sport'),
    ('weather', 'Wetter'),
    ('navigation', 'Navigation'),
    ('communication', 'Kommunikation'),
    ('other', 'Andere'),
]

SUB_CATEGORY_CHOICES = [
    ('none', 'Keine Unterkategorie'),       
    ('action', 'Action'),
    ('adventure', 'Abenteuer'),
    ('puzzle', 'Puzzle'),
    ('strategy', 'Strategie'),
    ('simulation', 'Simulation'),
    ('arcade', 'Arcade'),
    ('racing', 'Rennspiele'),
    ('role_playing', 'Rollenspiele'),
    ('sports_games', 'Sportspiele'),
    ('card_games', 'Kartenspiele'),
    ('board_games', 'Brettspiele'),
    ('casual_games', 'Casual Spiele'),
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
    if value.count() < 1:
        raise ValidationError("Mindestens 1 Screenshots erforderlich.")

class App(models.Model):
    developer = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name='apps')
    name = models.CharField(max_length=255)
    description = models.TextField()
    language = models.CharField(max_length=5, choices=LANGUAGES, default='de')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    age_rating = models.CharField(max_length=2, choices=AGE_RATINGS, default='0')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    subcategory = models.CharField(max_length=50, choices=SUB_CATEGORY_CHOICES, blank=True)
    icon = models.ImageField(upload_to='app_icons/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    download_count = models.PositiveIntegerField(default=0)  # NEU

    def __str__(self):
        return f"{self.name} ({self.developer.name}) - {self.platform}"
    
class VersionDownload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    version = models.ForeignKey('Version', on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'version')

    def __str__(self):
        return f"{self.user.username} downloaded {self.version.app.name} v{self.version.version_number} on {self.downloaded_at.strftime('%Y-%m-%d %H:%M:%S')}"

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
    new_version = models.BooleanField(default=False)  # Markierung für neue Version

    def __str__(self):
        return f"{self.app.name} v{self.version_number} on {self.app.platform}"

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

    # Neue Felder, die deiner Funktion entsprechen:
    app = models.ForeignKey('App', on_delete=models.CASCADE, null=True, blank=True)
    version = models.ForeignKey('Version', on_delete=models.CASCADE, null=True, blank=True)
    level = models.CharField(max_length=20, default='info')  # info, success, warning, error
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.title} -> {"Alle" if not self.user else self.user.username}'
    
class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    endpoint = models.TextField(unique=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.endpoint[:40]
    
class AppInfo(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return f"{self.name}"


class AppUpdate(models.Model):
    UPDATE_TYPES = [
        ("info", "Information"),
        ("warnung", "Warnung"),
        ("kritisch", "Kritisch"),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    update_type = models.CharField(max_length=10, choices=UPDATE_TYPES)
    date = models.DateField(auto_now_add=True)
    link = models.URLField(blank=True)

    def __str__(self):
        return f"[{self.get_update_type_display()}] {self.title}"


class RoadmapItem(models.Model):
    STATUS_CHOICES = [
        ("geplant", "Geplant"),
        ("in_arbeit", "In Arbeit"),
        ("abgeschlossen", "Abgeschlossen"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    date = models.DateField()

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"