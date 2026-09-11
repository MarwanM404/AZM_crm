"""Administrator management of staff accounts, departments, and branches (FR-025)."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import Branch, Department, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = ["email", "full_name", "role", "department", "branch", "is_active"]
    list_filter = ["role", "department", "branch", "is_active"]
    search_fields = ["email", "full_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "role", "department", "branch", "language")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "role",
                    "department",
                    "branch",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
