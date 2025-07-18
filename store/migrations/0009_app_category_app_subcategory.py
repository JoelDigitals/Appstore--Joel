# Generated by Django 5.2.1 on 2025-07-09 00:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0008_app_download_count_versiondownload'),
    ]

    operations = [
        migrations.AddField(
            model_name='app',
            name='category',
            field=models.CharField(choices=[('games', 'Spiele'), ('productivity', 'Produktivität'), ('education', 'Bildung'), ('entertainment', 'Unterhaltung'), ('utilities', 'Dienstprogramme'), ('social', 'Soziale Netzwerke'), ('health', 'Gesundheit'), ('lifestyle', 'Lebensstil'), ('finance', 'Finanzen'), ('travel', 'Reisen'), ('news', 'Nachrichten'), ('music', 'Musik'), ('photo_video', 'Foto & Video'), ('books', 'Bücher'), ('shopping', 'Einkaufen'), ('food_drink', 'Essen & Trinken'), ('sports', 'Sport'), ('weather', 'Wetter'), ('navigation', 'Navigation'), ('communication', 'Kommunikation'), ('other', 'Andere')], default='other', max_length=50),
        ),
        migrations.AddField(
            model_name='app',
            name='subcategory',
            field=models.CharField(blank=True, choices=[('action', 'Action'), ('adventure', 'Abenteuer'), ('puzzle', 'Puzzle'), ('strategy', 'Strategie'), ('simulation', 'Simulation'), ('arcade', 'Arcade'), ('racing', 'Rennspiele'), ('role_playing', 'Rollenspiele'), ('sports_games', 'Sportspiele'), ('card_games', 'Kartenspiele'), ('board_games', 'Brettspiele'), ('casual_games', 'Casual Spiele')], max_length=50),
        ),
    ]
