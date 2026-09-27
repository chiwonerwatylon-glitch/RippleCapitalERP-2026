# companies/admin.py
from django.contrib import admin
from .models import InsuranceCompany, ClassOfBusiness


class ClassOfBusinessInline(admin.TabularInline):
    model = ClassOfBusiness
    extra = 0


@admin.register(InsuranceCompany)
class InsuranceCompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "short_code", "contact_email", "contact_phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "short_code", "contact_email", "contact_phone")
    inlines = [ClassOfBusinessInline]
    readonly_fields = ("created_at",)


@admin.register(ClassOfBusiness)
class ClassOfBusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "insurance_company", "default_commission_rate")
    list_filter = ("insurance_company",)
    search_fields = ("name", "insurance_company__name", "insurance_company__short_code")
