from django.contrib import admin
from django_q.tasks import async_task
from .models import CuratedProduct

@admin.register(CuratedProduct)
class CuratedProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'merchant', 'price', 'is_in_stock', 'last_synced')
    list_filter = ('is_in_stock', 'merchant')
    search_fields = ('title', 'merchant_product_id', 'merchant')
    readonly_fields = ('last_synced',)
    
    actions = ['trigger_manual_sync']

    @admin.action(description="Force manual Awin sync now")
    def trigger_manual_sync(self, request, queryset):
        # Dispatches the task to your background worker immediately
        async_task('products.tasks.automated_product_sync')
        self.message_user(request, "Sync task sent to the background worker. Give it a few seconds!")