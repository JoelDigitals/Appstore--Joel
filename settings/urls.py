from django.urls import path
from . import views

urlpatterns = [
    path('', views.user_profile_view, name='user_profile'),
    path('edit/', views.edit_user_profile_view, name='edit_user_profile'),
    path('delete/', views.delete_user_profile_view, name='delete_user_profile'),
    path('settings/', views.user_settings_view, name='user_settings'),
    path('settings/notifications/', views.notification_settings_view, name='notification_settings'),
    path('settings/security/', views.security_settings, name='security_settings'),

]
