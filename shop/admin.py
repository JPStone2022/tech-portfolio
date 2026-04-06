from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'short_description', 'description')
    prepopulated_fields = {'slug': ('title',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'short_description', 'description', 'is_published')
        }),
        ('Pricing & Asset', {
            'fields': ('price', 'cover_image')
        }),
        ('Headless Routing (Composable Commerce)', {
            'fields': ('external_buy_url',)
        }),
        ('Affiliate Integration', {
            'fields': ('related_affiliate_product_name', 'related_affiliate_link', 'affiliate_pitch')
        }),
    )