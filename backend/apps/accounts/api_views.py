from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


def _serialize_user(user):
    organization = getattr(user, 'organization', None)
    return {
        'id': str(user.pk),
        'email': user.email,
        'full_name': user.get_full_name() or user.username,
        'role': user.role,
        'hospital_id': organization.tenant_id if organization else '',
        'avatar_url': '',
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    email = (request.data.get('email') or '').strip().lower()
    password = request.data.get('password') or ''
    role = (request.data.get('role') or '').strip()
    hospital_id = (request.data.get('hospital_id') or '').strip()

    if not email or not password:
        return Response(
            {'detail': 'Email and password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Support login by email while Django auth backend authenticates by username.
    user = authenticate(request, username=email, password=password)

    if user is None:
        user_model = get_user_model()
        candidate = user_model.objects.filter(email__iexact=email).first()
        if candidate is not None:
            user = authenticate(request, username=candidate.username, password=password)

    if user is None:
        return Response(
            {'detail': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if role and user.role != role:
        return Response(
            {'detail': 'Role does not match this account.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    user_org = getattr(user, 'organization', None)
    if hospital_id and user_org and user_org.tenant_id != hospital_id:
        return Response(
            {'detail': 'Hospital ID does not match this account.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    refresh = RefreshToken.for_user(user)
    update_last_login(None, user)

    return Response(
        {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': _serialize_user(user),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_api(request):
    return Response(_serialize_user(request.user), status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_api(request):
    refresh_token = request.data.get('refresh')
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            # Best effort logout; client always removes local tokens.
            pass

    return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_api(request):
    # Generic success response prevents account enumeration.
    return Response(
        {'detail': 'If the email exists, a reset link has been sent.'},
        status=status.HTTP_200_OK,
    )
