from django.urls import path
from .views import *

urlpatterns = [
    path("login/", loginUser, name="login"),
    path("signup/", signupUser, name="signup"),
    path("logout/", logoutUser, name="logout"),
    
    # API endpoints
    path("api/check-username/", check_username, name="check_username"),
    path("api/validate-password/", validate_password, name="validate_password"),
    path("api/check_login", check_login, name="check_login"),
]