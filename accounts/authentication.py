from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .jwt import decode_access_token
from .models import User


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise AuthenticationFailed('Invalid authentication credentials')

        token = parts[1]
        payload = decode_access_token(token)

        if payload is None:
            raise AuthenticationFailed('Invalid authentication credentials')

        user_id = payload.get('sub')
        if user_id is None:
            raise AuthenticationFailed('Invalid token payload')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found')

        return (user, None)

    def authenticate_header(self, request):
        return 'Bearer'
