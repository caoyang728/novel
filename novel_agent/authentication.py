"""
Custom JWT authentication that doesn't fail if no token is provided.
"""
import jwt
from loguru import logger
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.permissions import BasePermission
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseForbidden
from rest_framework import authentication, status
from rest_framework.exceptions import AuthenticationFailed


class JWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError):
            return None


class AllowAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


