from django.db import models
from django.urls import reverse

from core.models import SluggedModel, FeaturedProductsMixin, InfographicContentMixin, TimestampedModel, ImageMixin, HomepageFeaturedMixin, SEOMixin


class TechBootcamp(ImageMixin, FeaturedProductsMixin, HomepageFeaturedMixin, SEOMixin):
    CATEGORY_CHOICES = [
        ('AI', 'Artificial Intelligence'),
        ('DS', 'Data Science'),
        ('WEB', 'Python & Django'),
        ('TECH', 'General Tech'),
    ]
    title = models.CharField(max_length=250, help_text="The main title of the bootcamp/guide.")
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    level = models.CharField(max_length=50, default="beginner", help_text="e.g., Beginner, Junior, Intermediate")
    target_skill = models.CharField(max_length=250, blank=True, help_text="e.g., Python, Django, React")
    
    description = models.TextField(blank=True, help_text="Short summary.")
    long_description = models.TextField(blank=True, help_text="Long marketing description.")
    
    is_published = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=True)

    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='TECH')

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

class BootcampWeek(models.Model):
    bootcamp = models.ForeignKey(TechBootcamp, on_delete=models.CASCADE, related_name='weeks')
    week_number = models.PositiveIntegerField()
    title = models.CharField(max_length=250, help_text="e.g., 'Week 1: Python Fundamentals'")
    focus = models.TextField(blank=True, help_text="The technical learning goal for this week.")

    class Meta:
        ordering = ['week_number']
        unique_together = ('bootcamp', 'week_number')

    def __str__(self):
        return f"{self.bootcamp.title} - Week {self.week_number}"

class BootcampDay(models.Model):
    week = models.ForeignKey(BootcampWeek, on_delete=models.CASCADE, related_name='days')
    day_number = models.PositiveSmallIntegerField(help_text="Day 1-7")
    title = models.CharField(max_length=250, help_text="e.g., 'Understanding For-Loops'")
    
    theory_lesson = models.TextField(blank=True, help_text="The concept explained. Supports Markdown.")
    coding_exercise = models.TextField(blank=True, help_text="A practical code snippet or challenge. Supports Markdown.")
    real_world_application = models.TextField(blank=True, help_text="How this is used in actual apps. Supports Markdown.")
    mindset_focus = models.TextField(blank=True, help_text="A tip for debugging, imposter syndrome, or focus.")
    is_rest_day = models.BooleanField(default=False, help_text="Check if this is a consolidation/rest day.")
    class Meta:
        ordering = ['day_number']
        unique_together = ('week', 'day_number')

    def __str__(self):
        return f"{self.week.bootcamp.title} - Week {self.week.week_number} Day {self.day_number}"
    
class TechSkill(models.Model):
    CATEGORY_CHOICES = [
        ('AI', 'Artificial Intelligence & LLMs'),
        ('BACKEND', 'Backend Architecture'),
        ('FRONTEND', 'Frontend & UI'),
        ('DEVOPS', 'DevOps & CI/CD'),
        ('DATABASE', 'Database & Caching'),
        ('LIBRARY', 'Key Python Libraries'),
    ]

    name = models.CharField(max_length=100)
    icon_class = models.CharField(
        max_length=100, 
        help_text="FontAwesome class, e.g., 'fa-brands fa-python' or 'fa-solid fa-server'"
    )
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=255, blank=True)
    
    is_key_library = models.BooleanField(default=False, help_text="Feature this in the Ecosystem section.")
    usage_explanation = models.TextField(blank=True, help_text="How this is utilized in this project.")
    doc_link = models.URLField(blank=True, help_text="Link to official docs.")
    
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.name

class ProjectFeature(models.Model):
    title = models.CharField(max_length=250)
    slug = models.SlugField(unique=True)
    description = models.TextField(help_text="High-level summary of the feature.")
    challenge = models.TextField(help_text="The Problem: Why was this difficult?")
    solution = models.TextField(help_text="The Fix: How did you solve it technically?")
    
    technology_used = models.ManyToManyField(TechSkill, related_name='features')
    
    demo_link = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title
