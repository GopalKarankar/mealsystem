import logging
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from django.conf import settings

from .models import User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    GoogleLoginSerializer,
    TokenResponseSerializer,
)
from .jwt import create_access_token
from .google_oauth import generate_unique_username

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            # Return 400 with first error message found
            for field, errors in serializer.errors.items():
                error_msg = errors[0] if isinstance(errors, list) else errors
                return Response(
                    {"detail": str(error_msg)},
                    status=status.HTTP_400_BAD_REQUEST
                )

        username = serializer.validated_data['username']
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        # Generate JWT token
        token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(seconds=settings.JWT_EXPIRY_SECONDS),
        )

        response_data = {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "expires_in": settings.JWT_EXPIRY_SECONDS,
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"detail": "Invalid request"},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Try to authenticate using email
        try:
            user = User.objects.get(email=email)
            if not user.check_password(password):
                return Response(
                    {"detail": "Invalid email or password"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate JWT token
        token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(seconds=settings.JWT_EXPIRY_SECONDS),
        )

        response_data = {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "expires_in": settings.JWT_EXPIRY_SECONDS,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class GoogleLoginView(APIView):
    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"detail": "Invalid request"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not settings.GOOGLE_CLIENT_ID:
            return Response(
                {"detail": "Google login is not configured"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        id_token_str = serializer.validated_data['id_token']

        try:
            # Verify token with Google
            idinfo = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as e:
            logger.warning("Google token verification failed: %s", str(e))
            detail = f"Invalid Google token: {e}" if settings.DEBUG else "Invalid Google token"
            return Response(
                {"detail": detail},
                status=status.HTTP_401_UNAUTHORIZED
            )

        google_id = idinfo.get("sub")
        email = idinfo.get("email")
        name = idinfo.get("name", "")

        if not google_id or not email:
            return Response(
                {"detail": "Invalid Google token data"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Find or create user
        user = User.objects.filter(google_id=google_id).first()

        if user is None:
            # Try to find by email
            user = User.objects.filter(email=email).first()

            if user is not None:
                # Existing user, link Google ID
                user.google_id = google_id
                user.save()
            else:
                # Create new user
                username = generate_unique_username(email.split("@")[0])
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=None,  # OAuth user, no password
                    google_id=google_id,
                    first_name=name,
                )

        # Generate JWT token
        token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(seconds=settings.JWT_EXPIRY_SECONDS),
        )

        response_data = {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "expires_in": settings.JWT_EXPIRY_SECONDS,
        }

        return Response(response_data, status=status.HTTP_200_OK)
