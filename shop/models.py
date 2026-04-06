from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.text import slugify
import uuid

class Product(models.Model):
    """
    Portfolio Showcase & Routing Model.
    Does not handle direct payments or secure file hosting.
    """
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    short_description = models.CharField(max_length=255, help_text="Displayed on the card view.")
    description = models.TextField(help_text="Full details. Markdown is supported.")
    
    # Pricing (For display purposes)
    price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Price (GBP £)")

    # The Asset (Switched to URLField for AI Script compatibility)
    cover_image = models.URLField(max_length=500, blank=True, null=True, help_text="URL to the cover image")
    
    # --- COMPOSABLE COMMERCE ROUTING ---
    external_buy_url = models.URLField(
        max_length=500, 
        blank=True, 
        help_text="If this is a real product, paste the Stripe/Checkout URL from your main PT site here."
    )
    
    # Affiliate Integration (Cross-selling)
    related_affiliate_product_name = models.CharField(max_length=255, blank=True)
    related_affiliate_link = models.URLField(blank=True)
    affiliate_pitch = models.CharField(max_length=255, blank=True)

    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


##### Purchase model

class Purchase(models.Model):
    """Simple record of ownership."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='purchases')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchases')
    purchased_at = models.DateTimeField(auto_now_add=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-purchased_at']
        unique_together = ('user', 'product') # Prevent duplicate purchases of same digital item

    def __str__(self):
        return f"{self.user.email} - {self.product.title}"
