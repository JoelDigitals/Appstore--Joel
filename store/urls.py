from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('developer/dashboard/', views.developer_dashboard, name='developer_dashboard'),
    path('developer/apps/', views.developer_dashboard, name='developer_apps'),  # Alias für Übersicht der Apps des Developers
    path('developer/neu/', views.create_developer_view, name='create_developer'),
    path('developer/<int:developer_id>/edit/', views.edit_developer_view, name='edit_developer'),
    path('developer/<int:developer_id>/delete/', views.delete_developer_view, name='delete_developer'),
    path('developer/<int:version_id>/check/', views.version_status_view, name='version_status_view'),
    path('developer/<str:name>/', views.developer_detail_view, name='developer_detail'),
    path('developer/app/<int:app_id>/', views.app_detail_dev_view, name='app_detail_dev'),
    path('developer/app/<int:app_id>/screenshots/', views.app_screenshots_view, name='app_screenshots'),
    path('developer/app/<int:app_id>/screenshots/upload/', views.upload_screenshots_view, name='upload_screenshots'),
    path('developer/app/<int:app_id>/edit/', views.edit_app_view, name='edit_app'),
    path('developer/app/<int:app_id>/delete/', views.delete_app_view, name='delete_app'),
    path('developer/app/<int:app_id>/upload-version/', views.upload_version, name='upload_version'),

    path('download/media/', views.download_all_media, name='download_media'),


    path('app/create/', views.create_app_view, name='create_app'),
    path('', views.home, name='home'),
    path('platform/<str:platform_name>/', views.platform_view, name='platform'),
    path('app/<int:app_id>/', views.app_detail_view, name='app_detail'),

    path('app/<int:app_id>/upload-version/', views.upload_version, name='upload_version'),

    path('app/<int:app_id>/', views.app_detail_view, name='app_detail'),
    path('download/<int:version_id>/', views.download_app_view, name='download_app'),
    path('download/<int:version_id>/success/', views.download_success_view, name='download_success'),
    path('download/<int:version_id>/file/', views.download_file_view, name='download_file'),
    
    path('save-subscription/', views.save_subscription, name='save_subscription'),

    path('accounts/login/', views.login_view, name='login'),
]
