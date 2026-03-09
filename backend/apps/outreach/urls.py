from django.urls import path

from . import views

app_name = 'outreach'

urlpatterns = [
    path('webhook/whatsapp/', views.whatsapp_webhook, name='whatsapp_webhook'),
]
