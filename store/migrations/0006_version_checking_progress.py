# Generated by Django 5.2.1 on 2025-07-06 17:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0005_appscreenshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='version',
            name='checking_progress',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
