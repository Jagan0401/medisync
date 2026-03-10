from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import api_views


urlpatterns = [
    path('login/', api_views.login_api, name='api_login'),
    path('me/', api_views.me_api, name='api_me'),
    path('logout/', api_views.logout_api, name='api_logout'),
    path('password-reset/', api_views.password_reset_api, name='api_password_reset'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
