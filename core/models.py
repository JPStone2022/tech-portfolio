from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from django.urls import reverse
from django.utils.html import mark_safe
from django.templatetags.static import static
from django.contrib import admin
from django.core.cache import cache
import random

#### Timestamped model --- Blueprint 1: Automatic Timestamps ---


##### Blueprint 1: TimestampedModel
# Purpose: This is an abstract model designed to automatically track when an object is created and when it was last updated. Any model that inherits from this will get two fields without you having to define them every time.

# Key Fields:

# created_at: Automatically set to the current date and time only when the object is first created.

# updated_at: Automatically updated to the current date and time every time the object is saved.

# Usage: You would use this for any content where knowing its age or last modification date is important, like blog posts, user profiles, or articles.


class TimestampedModel(models.Model):
    """
    An abstract model that provides self-updating `created_at` and `updated_at` fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


##### Slugged model --- Blueprint 2: Name and Auto-Slug ---


##### Blueprint 2: SluggedModel
# Purpose: This abstract model provides a name field and automatically generates a URL-friendly slug from that name. Slugs are what you typically see in a web address (e.g., .../my-first-blog-post).

# Key Fields:

# name: A simple character field for a title or name.

# slug: A SlugField that will be auto-populated based on the name.

# Key Logic:

# The save() method is customized. If you create an object with a name but don't provide a slug, it will create one for you (e.g., "My New Post" becomes "my-new-post").

# It also cleverly handles duplicates. If you create another post named "My New Post", it will automatically save the slug as "my-new-post-1" to ensure every URL is unique.

class SluggedModel(models.Model):
    """
    An abstract model that provides a `name` and a self-generating `slug` field.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-generate slug if it's not set
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Ensure the slug is unique by appending a counter if it already exists.
        # This check only runs when the object is first created.
        if self.pk is None:
            original_slug = self.slug
            counter = 1
            # Keep trying new slugs until we find one that is unique
            while self.__class__.objects.filter(slug=self.slug).exists():
                self.slug = f'{original_slug}-{counter}'
                counter += 1
        
        super().save(*args, **kwargs)


##### Featured Products model --- Blueprint 3: Featured Affiliate Products ---


##### Blueprint 3: FeaturedProductsMixin
# Purpose: This is a mixin, a special kind of class that "mixes in" specific fields and methods. Its job is to add the ability to link a piece of content to related affiliate products. It thoughtfully includes separate fields for UK and US markets.

# Key Methods:

# get_featured_slugs_as_list(): A helper method that takes the comma-separated string of slugs (e.g., "product-a, product-b") and turns it into a clean Python list (['product-a', 'product-b']), which is much easier to work with in your code.

class FeaturedProductsMixin(models.Model):
    
    class Meta:
        abstract = True

    def get_regional_featured_products(self, region='UK', limit=3):
            cache_key = f"featured_products_{self._meta.model_name}_{self.pk}_{region}"
            
            cached_products = cache.get(cache_key)
            if cached_products:
                return cached_products

            from affiliates.models import AffiliateProduct 

            # 1. Base query: Find available products ONLY from Recommended Partners!
            qs = AffiliateProduct.objects.filter(
                variants__is_available=True,
                merchant__is_recommended_partner=True  # <--- NEW FILTER ADDED HERE
            )

            if region == 'US':
                qs = qs.exclude(variants__buy_url_us__exact='').exclude(variants__buy_url_us__isnull=True)
            elif region == 'EU':
                qs = qs.exclude(variants__buy_url_eu__exact='').exclude(variants__buy_url_eu__isnull=True)
            else:
                qs = qs.exclude(variants__buy_url__exact='').exclude(variants__buy_url__isnull=True)

            # Get a flat list of unique IDs
            valid_ids = list(qs.values_list('id', flat=True).distinct())

            if not valid_ids:
                return []

            # 2. Pick random IDs using Python
            import random
            random_ids = random.sample(valid_ids, min(len(valid_ids), limit))

            # 3. Fetch ONLY those products, and pre-package their Brands and Variants
            products = list(
                AffiliateProduct.objects.filter(id__in=random_ids)
                .select_related('brand', 'category')
                .prefetch_related('variants', 'deals')
            )

            # 4. Save to the cache
            cache.set(cache_key, products, timeout=86400)

            return products


##### Image Mixin model --- Blueprint 4: Common Image Fields ---


#### Blueprint 4: ImageMixin
# Purpose: This mixin provides a standardized way to handle images for any model. It's built for both efficiency and flexibility.

# Key Fields:

# image: A standard ImageField for uploading images, which are stored in a cloud service like Dropbox. This is for dynamic, user-controlled content.

# static_image_path: A simple text field where you can put a path to an image that's already part of your site's static files (e.g., images/default.jpg).

# Key Logic (get_image_url): This is the most important part. When you ask for an object's image, it follows a priority system:

# It first checks if a static_image_path is defined. These images load very fast, so they are preferred.

# If not, it checks if a user has uploaded an image to Dropbox and returns that URL.

# If neither exists, it provides a default placeholder image so you never have a broken image link.

class ImageMixin(models.Model):
    """
    A mixin for models that have a primary image.
    Provides an `image` field for user-uploaded media (via Dropbox)
    and a `static_image_path` for fast-loading static images.
    """
    # For dynamic, user-uploaded images (handled by Dropbox)
    image = models.ImageField(
        upload_to='images/%Y/%m/',
        blank=True,
        null=True,
        help_text="Upload a unique image for this item. This will be stored on Dropbox."
    )
    # For static, design-related images (handled by WhiteNoise)
    static_image_path = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Path to a static image (e.g., 'portfolio/images/hero.jpg'). This is faster and overrides the uploaded image."
    )

    class Meta:
        abstract = True

    @property
    def get_image_url(self):
        """
        Intelligently returns the correct image URL.
        Prioritises the fast static image, falls back to the dynamic Dropbox image,
        and finally provides a default placeholder.
        """
        if self.static_image_path:
            return static(self.static_image_path)
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        # Return a path to a default placeholder image in your static files
        return static('portfolio/images/placeholders/default-placeholder.png')

    def image_thumbnail(self):
        """
        Provides a thumbnail for the Django admin, using the same logic.
        """
        img_url = self.get_image_url
        if img_url:
            return mark_safe(f'<img src="{img_url}" width="100" />')
        return "No Image"
    image_thumbnail.short_description = 'Image Thumbnail'


##### Base Audio Table Content model --- Blueprint 5: Base for Content without Affiliate Links ---


##### Blueprint 5: BaseAuditableContentModel
# Purpose: Now we're starting to combine the Lego blocks. This is an abstract base model for any piece of content that needs basic features but does not need to link to affiliate products.

# Inherits from: TimestampedModel and ImageMixin.

# Gets: created_at, updated_at, image, and static_image_path.

# Adds: title, slug (with auto-generation), and description.

# Usage: This would be perfect for a simple model like a "Testimonial" or a "FAQ" entry, where you don't need to recommend gear.
    
class BaseAuditableContentModel(TimestampedModel, ImageMixin):
    """
    An abstract base for content that needs timestamps, an image, a title, slug, and description.
    Does NOT include the affiliate product fields.
    """
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta(TimestampedModel.Meta):
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Ensure slug uniqueness
        if self.pk is None: # New object
            original_slug = self.slug
            counter = 1
            while self.__class__.objects.filter(slug=self.slug).exists():
                self.slug = f'{original_slug}-{counter}'
                counter += 1
        super().save(*args, **kwargs)


##### Base Content model --- Blueprint 6: Base for Primary Content Types (with Affiliate Links) ---


##### Blueprint 6: BaseContentModel
# Purpose: This is the most comprehensive base model. It's intended for your primary content types like "Blog Posts", "Articles", or "Exercises", which need all the core features.

# Inherits from: BaseAuditableContentModel and FeaturedProductsMixin.

# Gets: Everything from BaseAuditableContentModel (timestamps, images, title, slug, description) and everything from FeaturedProductsMixin (the UK and US featured product fields).

# Usage: This is the blueprint you'd use for most of the main content on your site.

class BaseContentModel(BaseAuditableContentModel, FeaturedProductsMixin):
    """
    A comprehensive abstract base model for primary content types.
    Inherits everything from BaseAuditableContentModel and adds affiliate product fields.
    """
    class Meta(BaseAuditableContentModel.Meta):
        abstract = True


##### Infographic Content Mixin model --- Blueprint 7: Infographic Content ---


##### Blueprint 7: InfographicContentMixin
# Purpose: This is a very specialized mixin. It's designed to store the raw code from an infographic that has been parsed. This allows you to embed complex, styled content directly into a page.

# Key Fields:

# content_html: Stores the HTML part.

# style_tags_content: Stores the CSS styles.

# extra_scripts_html: Stores any necessary JavaScript.

class InfographicContentMixin(models.Model):
    """
    A mixin for models that store raw HTML/CSS content parsed from
    infographic-style files.
    """
    content_html  = models.TextField(blank=True, help_text="Raw HTML content from a parsed infographic file.")
    style_tags_content = models.TextField(blank=True, help_text="Raw CSS content from a parsed infographic file.")
    extra_scripts_html = models.TextField(blank=True, help_text="Raw js content from a parsed infographic file.")

    class Meta:
        abstract = True

# Add this new Mixin to each model that requires the new homepage featured flag

##### Homepage Featured Mixin model --- Blueprint for Homepage Featuring ---


##### Blueprint 8: HomepageFeaturedMixin
# Purpose: A very simple but useful mixin. It adds a single checkbox in the admin panel.

# Key Field:

# is_homepage_featured: A simple True/False field.

# Usage: You can add this to any content model (like Articles or Programs). Checking the box for an item will flag it, allowing you to easily pull it for display in the "Knowledge Hub" section of your homepage.

class HomepageFeaturedMixin(models.Model):
    """
    An abstract mixin that provides a simple boolean field to flag an item
    for featuring on the main homepage.
    """
    is_homepage_featured = models.BooleanField(
        default=False,
        help_text="Check this to feature this item in the 'Knowledge Hub' on the homepage."
    )

    class Meta:
        abstract = True


##### SEO Mixin model --- Blueprint for SEO Fields ---


##### Blueprint 9: SEOMixin
# Purpose: This mixin provides dedicated fields for Search Engine Optimisation (SEO). This allows you to write custom, SEO-friendly titles and descriptions for your pages that might be different from the main on-page title and description.

# Key Fields:

# seo_title: For the <title> tag in HTML.

# meta_description: For the <meta name="description"> tag.

# meta_keywords: For the <meta name="keywords"> tag.

class SEOMixin(models.Model):
    """
    An abstract mixin that provides fields for SEO meta tags.

    """
    # It's best to move these changes to the SEOMixin in core/models.py for project-wide consistency.
    seo_title = models.CharField(max_length=255, blank=True, null=True, help_text="SEO Title for the recommendation's detail page.")
    meta_description = models.TextField(blank=True, null=True, help_text="SEO Meta Description for the detail page.")
    meta_keywords = models.CharField(max_length=255, blank=True, null=True, help_text="SEO Meta Keywords for the detail page.")

    class Meta:
        abstract = True

