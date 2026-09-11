"""
Read-only audit log (FR-028, FR-029; T112/T114).

django-auditlog's LogEntry is registered here explicitly rather than relying on any default,
and every mutating permission is denied so no role, including administrator, can edit or
delete an audit entry.
"""

from auditlog.models import LogEntry
from django.contrib import admin

# django-auditlog registers its own LogEntryAdmin by default; replace it so we can enforce
# read-only permissions (FR-028) rather than accepting whatever its default allows.
if admin.site.is_registered(LogEntry):
    admin.site.unregister(LogEntry)


@admin.register(LogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "actor", "content_type", "object_repr", "action"]
    list_filter = ["action", "content_type"]
    search_fields = ["object_repr", "actor__email"]
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
