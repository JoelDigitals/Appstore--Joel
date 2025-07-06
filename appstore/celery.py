import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'appstore.settings')

app = Celery('appstore')

# Hier definierst du den Message Broker – Redis
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tasks automatisch aus allen Apps laden
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
