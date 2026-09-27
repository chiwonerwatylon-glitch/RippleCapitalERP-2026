"""
commissions/admin.py

Django Admin configuration for the Commissions app.
"""

import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import Commission, CommissionAdjustment, AgentCommissionPayout, CommissionStatus


# ======================================================================
# INLINE: CommissionAdjustment in Commission detail
# ======================================================================
class CommissionAdjustmentInline(admin.TabularInline):
    model = CommissionAdjustment
    extra = 0
    fields = ("reason", "adjustment_amount", "adjusted_by", "created_at")
    readonly_fields = ("reason", "adjustment_amount", "adjusted_by", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        # Adjustments should be created via services, not by hand.
        return False


# ======================================================================
# COMMISSION ADMIN
# ======================================================================
@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "policy_number_display",
        "client_name_display",
        "insurance_company_display",
        "agent_display",
        "rate_display",
        "amount_display",
        "status_badge",
        "settlement_display",
        "created_at",
    )

    list_filter = (
        "status",
        "policy__insurance_company",
        "policy__class_of_business",
        ("created_at", admin.DateFieldListFilter),
    )

    search_fields = (
        "policy__policy_number",
        "policy__client__full_name",
        "payment__receipt_number",
    )

    autocomplete_fields = ("policy", "payment", "disbursement", "agent_payout")

    readonly_fields = (
        "policy",
        "payment",
        "rate",
        "amount",
        "created_at",
        "confirmed_at",
        "disbursement",
        "agent_payout",
    )

    date_hierarchy = "created_at"

    inlines = [CommissionAdjustmentInline]

    actions = [
        "export_as_csv",
    ]

    fieldsets = (
        ("Source", {
            "fields": ("policy", "payment")
        }),
        ("Commission Details", {
            "fields": ("rate", "amount", "status")
        }),
        ("Links", {
            "fields": ("disbursement", "agent_payout")
        }),
        ("Timestamps", {
            "fields": ("created_at", "confirmed_at")
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "policy",
            "policy__client",
            "policy__insurance_company",
            "policy__agent",
            "payment",
            "disbursement",
        )

    # --- Display helpers ------------------------------------------------
    def policy_number_display(self, obj):
        return obj.policy.policy_number
    policy_number_display.short_description = "Policy No."
    policy_number_display.admin_order_field = "policy__policy_number"

    def client_name_display(self, obj):
        return obj.policy.client.full_name
    client_name_display.short_description = "Client"
    client_name_display.admin_order_field = "policy__client__full_name"

    def insurance_company_display(self, obj):
        return obj.policy.insurance_company.name
    insurance_company_display.short_description = "Insurer"
    insurance_company_display.admin_order_field = "policy__insurance_company__name"

    def agent_display(self, obj):
        agent = obj.policy.agent
        return agent.get_full_name() if agent else "—"
    agent_display.short_description = "Agent"

    def rate_display(self, obj):
        return f"{obj.rate}%"
    rate_display.short_description = "Rate"
    rate_display.admin_order_field = "rate"

    def amount_display(self, obj):
        return f"KES {obj.amount:,.2f}"
    amount_display.short_description = "Commission"
    amount_display.admin_order_field = "amount"

    def settlement_display(self, obj):
        if obj.disbursement:
            return format_html(
                '<span style="color:#1fa855;font-weight:600;">Settled in batch #{}</span>',
                obj.disbursement.id,
            )
        return format_html(
            '<span style="color:#c99b3c;">Not yet settled (insurer not fully remitted)</span>'
        )
    settlement_display.short_description = "Settlement / Remittance"

    def status_badge(self, obj):
        colors = {
            "PENDING": ("#fff8e6", "#c99b3c"),
            "CONFIRMED": ("#eafaf0", "#1fa855"),
            "REVERSED": ("#fff1f1", "#e5484d"),
            "SETTLED": ("#eef2ff", "#4f46e5"),
        }
        bg, fg = colors.get(obj.status, ("#f1f1f1", "#333333"))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:12px;font-weight:600;">{}</span>',
            bg, fg, obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    # --- Permissions: no manual add/delete -------------------------------
    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    # --- Bulk actions ----------------------------------------------------
    @admin.action(description="Export selected commissions to CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename=commissions_{timezone.now().date()}.csv'
        )
        writer = csv.writer(response)
        writer.writerow([
            "ID", "Policy Number", "Client", "Insurer", "Agent",
            "Rate (%)", "Amount", "Status", "Disbursement ID", "Created At",
        ])
        for c in queryset.select_related(
            "policy", "policy__client", "policy__insurance_company", "policy__agent", "disbursement"
        ):
            writer.writerow([
                c.id,
                c.policy.policy_number,
                c.policy.client.full_name,
                c.policy.insurance_company.name,
                c.policy.agent.get_full_name() if c.policy.agent else "",
                c.rate,
                c.amount,
                c.get_status_display(),
                c.disbursement.id if c.disbursement else "",
                c.created_at.isoformat(timespec="seconds"),
            ])
        return response


# ======================================================================
# COMMISSION ADJUSTMENT ADMIN
# ======================================================================
@admin.register(CommissionAdjustment)
class CommissionAdjustmentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "commission_link",
        "adjustment_amount_display",
        "reason",
        "adjusted_by",
        "created_at",
    )

    list_filter = (("created_at", admin.DateFieldListFilter), "reason")

    search_fields = (
        "commission__policy__policy_number",
        "reason",
        "notes",
        "adjusted_by__username",
    )

    readonly_fields = ("commission", "reason", "notes", "adjustment_amount", "adjusted_by", "created_at")

    date_hierarchy = "created_at"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("commission", "commission__policy", "adjusted_by")

    def commission_link(self, obj):
        return f"Commission #{obj.commission.id} — {obj.commission.policy.policy_number}"
    commission_link.short_description = "Commission"

    def adjustment_amount_display(self, obj):
        color = "#e5484d" if obj.adjustment_amount < 0 else "#1fa855"
        return format_html(
            '<span style="color:{};font-weight:600;">KES {:,.2f}</span>',
            color, obj.adjustment_amount,
        )
    adjustment_amount_display.short_description = "Adjustment"

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False


# ======================================================================
# AGENT COMMISSION PAYOUT ADMIN
# ======================================================================
class CommissionPayoutItemInline(admin.TabularInline):
    model = Commission
    fk_name = "agent_payout"
    extra = 0
    fields = ("policy", "amount", "status")
    readonly_fields = ("policy", "amount", "status")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AgentCommissionPayout)
class AgentCommissionPayoutAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "agent_display",
        "period_display",
        "total_amount_display",
        "status_badge",
        "paid_by",
        "paid_at",
    )

    list_filter = ("status", "agent")

    search_fields = ("agent__username", "agent__first_name", "agent__last_name")

    autocomplete_fields = ("agent", "paid_by")

    readonly_fields = ("total_amount", "created_at")

    date_hierarchy = "period_start"

    inlines = [CommissionPayoutItemInline]

    actions = ["mark_as_paid", "export_as_csv"]

    fieldsets = (
        ("Agent & Period", {
            "fields": ("agent", "period_start", "period_end")
        }),
        ("Amounts", {
            "fields": ("total_amount", "status")
        }),
        ("Payment Confirmation", {
            "fields": ("paid_by", "paid_at")
        }),
        ("Metadata", {
            "fields": ("created_at",)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("agent", "paid_by")

    def agent_display(self, obj):
        return obj.agent.get_full_name() or obj.agent.username
    agent_display.short_description = "Agent"
    agent_display.admin_order_field = "agent__username"

    def period_display(self, obj):
        return f"{obj.period_start} → {obj.period_end}"
    period_display.short_description = "Period"

    def total_amount_display(self, obj):
        return f"KES {obj.total_amount:,.2f}"
    total_amount_display.short_description = "Total Payout"
    total_amount_display.admin_order_field = "total_amount"

    def status_badge(self, obj):
        colors = {
            "PENDING": ("#fff8e6", "#c99b3c"),
            "PAID": ("#eafaf0", "#1fa855"),
        }
        bg, fg = colors.get(obj.status, ("#f1f1f1", "#333333"))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:12px;font-weight:600;">{}</span>',
            bg, fg, obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Mark selected payouts as PAID")
    def mark_as_paid(self, request, queryset):
        from .services import mark_payout_paid, CommissionServiceError

        updated = 0
        for payout in queryset:
            try:
                mark_payout_paid(payout, user=request.user)
                updated += 1
            except CommissionServiceError as exc:
                self.message_user(request, f"Could not mark payout #{payout.pk} as paid: {exc}", level="warning")
        self.message_user(request, f"{updated} payout(s) marked as paid.")

    @admin.action(description="Export selected payouts to CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename=agent_payouts_{timezone.now().date()}.csv'
        )
        writer = csv.writer(response)
        writer.writerow([
            "Agent", "Period Start", "Period End",
            "Total Amount", "Status", "Paid By", "Paid At",
        ])
        for p in queryset.select_related("agent", "paid_by"):
            writer.writerow([
                p.agent.get_full_name() or p.agent.username,
                p.period_start,
                p.period_end,
                p.total_amount,
                p.get_status_display(),
                p.paid_by.get_full_name() if p.paid_by else "",
                p.paid_at.strftime("%Y-%m-%d %H:%M") if p.paid_at else "",
            ])
        return response
