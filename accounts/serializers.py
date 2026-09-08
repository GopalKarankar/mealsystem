from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')


class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    token_type = serializers.CharField()
    user_id = serializers.CharField()
    expires_in = serializers.IntegerField()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        min_length=3,
        max_length=50,
        required=True,
    )
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
    )

    def validate_username(self, value):
        # Validate username format: alphanumeric and underscore only
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', value):
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, and underscores."
            )

        # Check if username already taken
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")

        return value

    def validate_email(self, value):
        # Check if email already registered
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except serializers.ValidationError:
            pass
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True)
