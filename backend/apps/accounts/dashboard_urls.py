from django.urls import path

from .dashboard_api import (
    doctor_dashboard_api,
    hospital_admin_dashboard_api,
    technician_dashboard_api,
    superadmin_dashboard_api,
)

urlpatterns = [
    path('doctor/', doctor_dashboard_api, name='api_doctor_dashboard'),
    path('hospital-admin/', hospital_admin_dashboard_api, name='api_hospital_admin_dashboard'),
    path('lab-tech/', technician_dashboard_api, name='api_technician_dashboard'),
    path('super-admin/', superadmin_dashboard_api, name='api_superadmin_dashboard'),
]
