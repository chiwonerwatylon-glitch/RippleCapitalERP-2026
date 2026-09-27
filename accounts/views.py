# accounts/views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from .forms import RippleLoginForm, UserCreateForm, UserUpdateForm
from .models import User
from core.mixins import AdminRequiredMixin


class RippleLoginView(LoginView):
    """
    Custom login view using RippleLoginForm and your login template.
    """
    template_name = "registration/login.html"
    authentication_form = RippleLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        remember_me = form.cleaned_data.get("remember_me")
        if not remember_me:
            self.request.session.set_expiry(0)  # browser close
        else:
            self.request.session.set_expiry(1209600)  # 2 weeks
        return super().form_valid(form)

    def get_success_url(self):
        # Route to core dashboard router
        return reverse_lazy("core:dashboard-home")


class RippleLogoutView(LogoutView):
    next_page = reverse_lazy("login")


class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 25

    def get_queryset(self):
        return User.objects.order_by("username")


class UserDetailView(AdminRequiredMixin, DetailView):
    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "user_obj"


class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def form_valid(self, form):
        messages.success(self.request, "User created successfully.")
        return super().form_valid(form)


class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def form_valid(self, form):
        messages.success(self.request, "User updated successfully.")
        return super().form_valid(form)
