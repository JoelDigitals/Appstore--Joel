from django import forms
from .models import App, AppWarning, Version, Developer, CATEGORY_CHOICES, SUB_CATEGORY_CHOICES, WARNING_TYPES
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'E-Mail-Adresse'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Benutzername'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['placeholder'] = 'Passwort'
        self.fields['password2'].widget.attrs['placeholder'] = 'Passwort bestätigen'
    

class AppEditForm(forms.ModelForm):
    # Optional: Du kannst hier Widgets oder Labels anpassen, z. B. für die Kategorien
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, label="Kategorie")
    subcategory = forms.ChoiceField(choices=SUB_CATEGORY_CHOICES, label="Unterkategorie", required=False)

    warning_types = forms.MultipleChoiceField(
        choices=WARNING_TYPES,
        widget=forms.CheckboxSelectMultiple,
        label="Warnung(en)",
        required=False
    )

    class Meta:
        model = App
        fields = ['name', 'description', 'language', 'platform', 'age_rating', 'icon', 'category', 'subcategory']

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance:
            initial = kwargs.setdefault('initial', {})
            initial['warning_types'] = [w.warning_type for w in instance.warnings.all()]
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        app = super().save(commit=False)
        if commit:
            app.save()
            # Vorhandene Warnungen löschen
            AppWarning.objects.filter(app=app).delete()
            # Neue Warnungen speichern
            selected_warnings = self.cleaned_data.get('warning_types', [])
            for wt in selected_warnings:
                AppWarning.objects.create(app=app, warning_type=wt)
        return app

class WarningForm(forms.ModelForm):
    class Meta:
        model = AppWarning
        fields = ['warning_type', 'description']

class VersionForm(forms.ModelForm):
    class Meta:
        model = Version
        fields = ['version_number', 'file', 'release_notes']

class DeveloperForm(forms.ModelForm):
    class Meta:
        model = Developer
        fields = [
            'name',
            'description',
            'website',
            'email',
            'logo',
            'youtube',
            'twitter',
            'github',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name des Entwicklers'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Kurzbeschreibung'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'support@example.com'
            }),
            'logo': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
            'youtube': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://youtube.com/channel/...'
            }),
            'twitter': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://twitter.com/username'
            }),
            'github': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://github.com/username'
            }),
        }

class AppWithVersionForm(forms.ModelForm):
    version_number = forms.CharField(max_length=50)
    file = forms.FileField()
    release_notes = forms.CharField(widget=forms.Textarea, required=False)
    published_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label="Geplante Veröffentlichungszeit (optional)"
    )

    # NEU: Kategorien
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, label="Kategorie")
    subcategory = forms.ChoiceField(choices=SUB_CATEGORY_CHOICES, label="Unterkategorie", required=False)

    # NEU: Mehrfachauswahl für Warnungen
    warning_types = forms.MultipleChoiceField(
        choices=WARNING_TYPES,
        widget=forms.CheckboxSelectMultiple,
        label="Warnung(en)",
        required=False
    )

    class Meta:
        model = App
        fields = ['name', 'description', 'language', 'platform', 'age_rating', 'icon', 'category', 'subcategory']

    def save(self, commit=True, developer=None):
        app = super().save(commit=False)
        if developer:
            app.developer = developer

        published_at = self.cleaned_data.get('published_at')
        app.published_at = published_at or timezone.now()

        if commit:
            app.save()

            # AppWarnings speichern
            selected_warnings = self.cleaned_data.get('warning_types', [])
            for wt in selected_warnings:
                AppWarning.objects.create(app=app, warning_type=wt)

        return app

    def save_version(self, app):
        version = Version(
            app=app,
            version_number=self.cleaned_data['version_number'],
            file=self.cleaned_data['file'],
            release_notes=self.cleaned_data['release_notes'],
            checking_status='pending',
            approved=False
        )
        version.save()
        return version