from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth import get_user_model

User = get_user_model()

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "phone", "role", "is_staff", "is_active")
    search_fields = ("username", "email", "phone")
    list_filter = ("role", "is_staff", "is_active")

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Extra", {"fields": ("phone", "role")}),
    )

    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Extra", {"fields": ("phone", "role")}),
    )
