from django import forms
from .models import App, AppWarning, Version, Developer

class AppForm(forms.ModelForm):
    class Meta:
        model = App
        fields = ['name', 'description', 'language', 'age_rating', 'icon']

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

    class Meta:
        model = App
        fields = ['name', 'description', 'language', 'platform', 'age_rating', 'icon']

    def save(self, commit=True, developer=None):
        app = super().save(commit=False)
        if developer:
            app.developer = developer
        if commit:
            app.save()
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
