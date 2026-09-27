# notifications/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from .models import NotificationLog
from .forms import NotificationFilterForm
from core.mixins import AdminRequiredMixin  # SUPERADMIN / COMPANY_ADMIN (or add ACCOUNTANT too)


class NotificationLogListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """
    Read-only list of all notifications sent to clients.

    Useful for audit and confirming that reminders were sent.
    """
    model = NotificationLog
    template_name = "notifications/notification_log_list.html"
    context_object_name = "notifications"
    paginate_by = 50

    def get_queryset(self):
        qs = NotificationLog.objects.select_related("client", "policy")
        form = NotificationFilterForm(self.request.GET or None)
        self.filter_form = form
        if form.is_valid():
            channel = form.cleaned_data.get("channel")
            nt = form.cleaned_data.get("notification_type")
            recipient = form.cleaned_data.get("recipient")
            if channel:
                qs = qs.filter(channel=channel)
            if nt:
                qs = qs.filter(notification_type=nt)
            if recipient:
                qs = qs.filter(recipient__icontains=recipient)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = getattr(self, "filter_form", NotificationFilterForm())
        return ctx
