from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    res = exception_handler(exc, context)
    if res and res.status_code == 401:
        return Response({"success":False, "message":"未登录或token已过期"}, status=status.HTTP_401_UNAUTHORIZED)
    return res