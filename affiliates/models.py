from django.db import models

class Merchant(models.Model):
    """The partner company (e.g., Amazon, Coursera, Julian Stone Institute)"""
    merchant_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class AffiliateCategory(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    
    class Meta:
        verbose_name_plural = "Affiliate Categories"

    def __str__(self):
        return self.name

class AffiliateProduct(models.Model):
    """The base product (e.g., 'Python Masterclass')"""
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(AffiliateCategory, on_delete=models.SET_NULL, null=True)
    
    base_product_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.base_product_name

class ProductVariant(models.Model):
    """The specific tier or version (e.g., 'Python Masterclass - Premium Tier')"""
    product = models.ForeignKey(AffiliateProduct, on_delete=models.CASCADE, related_name='variants')
    
    merchant_product_id = models.CharField(max_length=255, help_text="The ID/Slug used by the merchant")
    full_variant_name = models.CharField(max_length=255)
    
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    
    # The actual link the user clicks
    buy_url = models.URLField(max_length=500, help_text="The affiliate/routing URL")
    
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.full_variant_name