from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.conf import settings
from .models import UserProfile


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a new user account
    """
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not all([username, email, password]):
        return Response({
            'error': 'Username, email, and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({
            'error': 'Username already exists'
        }, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({
            'error': 'Email already exists'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Create user
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )

    # Create user profile with free tier
    UserProfile.objects.create(user=user, subscription_tier='free')

    # Create authentication token
    token, created = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'user_id': user.id,
        'username': user.username,
        'subscription_tier': 'free'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Authenticate user and return token
    """
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({
            'error': 'Username and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)

    if user:
        token, created = Token.objects.get_or_create(user=user)
        profile = UserProfile.objects.get_or_create(user=user)[0]

        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username,
            'subscription_tier': profile.subscription_tier
        })
    else:
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Get current user's profile information
    """
    profile = UserProfile.objects.get_or_create(user=request.user)[0]

    return Response({
        'user_id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
        'subscription_tier': profile.subscription_tier,
        'projects_created': profile.projects_created,
        'project_limit': profile.get_project_limit(),
        'review_collection_limit': profile.get_review_collection_limit(),
        'system_max_reviews': 2000,  # Hard system maximum
        'unlimited_dashboard_access': True,  # No monthly limits
        'data_refresh_policy': 'on-demand (when data is >24h old)',
        'enable_premium_dashboard': bool(getattr(settings, 'ENABLE_PREMIUM_DASHBOARD', False)),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Logout user by deleting their token
    """
    try:
        request.user.auth_token.delete()
        return Response({'message': 'Successfully logged out'})
    except:
        return Response({'error': 'Error logging out'}, status=status.HTTP_400_BAD_REQUEST)
