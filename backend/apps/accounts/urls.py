from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('superadmin/', views.superadmin_dashboard_view, name='superadmin'),
    path('hospital-admin/', views.hospital_admin_view, name='hospital_admin'),
    path('doctor/', views.doctor_view, name='doctor'),
    path('technician/', views.technician_view, name='technician'),
    # API endpoints for storing records
    path('api/patient/', views.api_add_patient, name='api_add_patient'),
    path('api/doctor/', views.api_add_doctor, name='api_add_doctor'),
    path('api/booking/', views.api_add_booking, name='api_add_booking'),
    path('api/appointment/', views.api_add_appointment, name='api_add_appointment'),
    path('api/followup/', views.api_add_followup, name='api_add_followup'),
    path('api/message/', views.api_send_message, name='api_send_message'),
    path('api/test-result/', views.api_add_test_result, name='api_add_test_result'),
    # Superadmin CRUD
    path('api/tenant/add/', views.api_add_tenant, name='api_add_tenant'),
    path('api/tenant/edit/', views.api_edit_tenant, name='api_edit_tenant'),
    path('api/tenant/delete/', views.api_delete_tenant, name='api_delete_tenant'),
    path('api/user/create/', views.api_create_user, name='api_create_user'),
    path('api/user/edit/', views.api_edit_user, name='api_edit_user'),
    path('api/user/delete/', views.api_delete_user, name='api_delete_user'),
    # Pipeline & WhatsApp
    path('api/pipeline/run/', views.api_run_pipeline, name='api_run_pipeline'),
    path('api/pipeline/status/', views.api_pipeline_status, name='api_pipeline_status'),
    path('api/hospital/feed/', views.api_hospital_feed, name='api_hospital_feed'),
    path('api/doctor/feed/', views.api_doctor_feed, name='api_doctor_feed'),
    path('api/technician/feed/', views.api_technician_feed, name='api_technician_feed'),
    path('api/booking/status/', views.api_update_booking_status, name='api_update_booking_status'),
    path('api/sample/status/', views.api_update_sample_status, name='api_update_sample_status'),
    path('api/translate/preview/', views.api_translate_preview, name='api_translate_preview'),
    path('api/whatsapp/send/', views.api_send_whatsapp, name='api_send_whatsapp'),
    path('api/whatsapp/webhook/', views.whatsapp_incoming_webhook, name='whatsapp_webhook'),
]
