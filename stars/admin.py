from django.contrib import admin, messages

from .models import ApiToken, Kid, QuickAction, StarRequest, StarTransaction


@admin.register(Kid)
class KidAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "balance", "user")
    raw_id_fields = ("user",)


@admin.register(QuickAction)
class QuickActionAdmin(admin.ModelAdmin):
    list_display = ("label", "delta", "order")


@admin.register(StarTransaction)
class StarTransactionAdmin(admin.ModelAdmin):
    list_display = ("kid", "delta", "reason", "created_at")
    list_filter = ("kid",)


@admin.register(StarRequest)
class StarRequestAdmin(admin.ModelAdmin):
    list_display = ("kid", "delta", "reason", "status", "created_at", "decided_by")
    list_filter = ("status", "kid")


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "prefix", "active", "created_at", "last_used_at")
    fields = ("name", "active")

    def save_model(self, request, obj, form, change):
        if not change:
            key = obj.set_new_key()
            messages.warning(
                request, f"API key for {obj.name}: {key} (copy it now; it won't be shown again)"
            )
        super().save_model(request, obj, form, change)
