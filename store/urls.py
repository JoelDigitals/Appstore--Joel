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
    path('developer/<int:version_id>/app/check/', views.version_status_app_view, name='version_app_status_view'),#
    path('developer/<int:version_id>/check/', views.version_status_view, name='version_status'),  # Alias für die Statusprüfung der App-Version
    path('developers/', views.developer_list, name='developer_list'),
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

    #download new urls
    path("api/download/<int:version_id>/", views.download_file_view, name="download_file_view"),
    path('api/download_complete/', views.download_complete, name='download_complete'),
    path('api/increment-download/', views.api_increment_download, name='api_increment_download'),


    #download old urls
    #path('download/start/<int:version_id>/', views.download_app_start, name='download_start'),
    #path('download/file/<int:version_id>/', views.download_file_view, name='download_file'),
    #path('download/complete/', views.download_complete, name='download_complete'),

    path("jds-appstore/", views.jds_appstore_apps, name="jds_apps"),

    path("save-subscription/", views.push_subscribe, name="push_subscribe"),
    path('notifications/check/', views.get_notifications_for_user, name='notifications_check'),
    path('notifications/', views.notifications_view, name='notifications_all'),
    path('notifications/subscribe/', views.subscribe_notifications, name='subscribe_notifications'),
    path('notifications/unsubscribe/', views.unsubscribe_notifications, name='unsubscribe_notifications'),
    path('notifications/<int:pk>/', views.notification_detail, name='notification_detail'),
    path('notifications/mark-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    path('accounts/login/', views.login_view, name='login'),

    path("status/api/<int:version_id>/", views.version_status_api, name="version_status_api"),

    path('my-installed-apps/', views.my_installed_apps, name='my_installed_apps'),

]
