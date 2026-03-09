from django.contrib import admin

from .models import Hospital


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant_id', 'is_active', 'created_at')
    search_fields = ('name', 'tenant_id')
