from django.contrib import admin

from .models import Kid, QuickAction, StarTransaction


@admin.register(Kid)
class KidAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "balance")


@admin.register(QuickAction)
class QuickActionAdmin(admin.ModelAdmin):
    list_display = ("label", "delta", "order")


@admin.register(StarTransaction)
class StarTransactionAdmin(admin.ModelAdmin):
    list_display = ("kid", "delta", "reason", "created_at")
    list_filter = ("kid",)
