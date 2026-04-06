from django.contrib import admin
from .models import Merchant, AffiliateCategory, AffiliateProduct, ProductVariant

@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('name', 'merchant_id')
    search_fields = ('name', 'merchant_id')

@admin.register(AffiliateCategory)
class AffiliateCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

# We use an Inline here so you can see the Variants directly inside the Product view!
class ProductVariantInline(admin.StackedInline):
    model = ProductVariant
    extra = 0

@admin.register(AffiliateProduct)
class AffiliateProductAdmin(admin.ModelAdmin):
    list_display = ('base_product_name', 'merchant', 'category', 'created_at')
    list_filter = ('merchant', 'category')
    search_fields = ('base_product_name',)
    prepopulated_fields = {'slug': ('base_product_name',)}
    inlines = [ProductVariantInline]