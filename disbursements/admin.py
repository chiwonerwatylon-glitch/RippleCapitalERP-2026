# disbursements/admin.py
from django.contrib import admin
from django.utils.html import format_html

from .models import Disbursement, DisbursementStatus


@admin.register(Disbursement)
class DisbursementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "insurance_company",
        "period_start",
        "period_end",
        "total_premium_collected",
        "total_commission",
        "net_amount_payable",
        "status_badge",
        "processed_by",
        "processed_at",
    )
    list_filter = ("status", "insurance_company", ("period_start", admin.DateFieldListFilter))
    search_fields = ("insurance_company__name", "insurance_company__short_code")
    readonly_fields = ("created_at",)

    def status_badge(self, obj):
        colors = {
            DisbursementStatus.PENDING: ("#fff8e6", "#c99b3c"),
            DisbursementStatus.PROCESSED: ("#eafaf0", "#1fa855"),
        }
        bg, fg = colors.get(obj.status, ("#f1f1f1", "#333"))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:10px;'
            'font-size:12px;font-weight:600;">{}</span>',
            bg, fg, obj.get_status_display(),
        )
    status_badge.short_description = "Status"
