from django.db import models
from django.utils import timezone

class CuratedProduct(models.Model):
    # Core Data
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    merchant = models.CharField(max_length=150, help_text="e.g., Rogue Fitness, Amazon")
    
    # The crucial unique ID from the affiliate network (Awin, ShareASale, etc.)
    merchant_product_id = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Affiliate Data
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    buy_url = models.URLField(max_length=1024)
    image_url = models.URLField(max_length=1024, blank=True)
    
    # Automation Tracking
    is_in_stock = models.BooleanField(default=True, db_index=True)
    last_synced = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-is_in_stock', 'title'] # Out of stock items drop to the bottom

    def __str__(self):
        return f"{self.title} ({'In Stock' if self.is_in_stock else 'OUT OF STOCK'})"