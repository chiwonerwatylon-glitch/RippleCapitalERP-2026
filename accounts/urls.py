# accounts/urls.py
from django.urls import path

from .views import (
    RippleLoginView,
    RippleLogoutView,
    UserListView,
    UserDetailView,
    UserCreateView,
    UserUpdateView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", RippleLoginView.as_view(), name="login"),
    path("logout/", RippleLogoutView.as_view(), name="logout"),

    # User management
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/add/", UserCreateView.as_view(), name="user_add"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="user_edit"),
]
