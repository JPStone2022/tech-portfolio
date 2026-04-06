from django.db import models
from django.urls import reverse

from core.models import SluggedModel, FeaturedProductsMixin, InfographicContentMixin, TimestampedModel, ImageMixin, HomepageFeaturedMixin, SEOMixin


##### AI Learning Path Models #####

class AILearningPath(ImageMixin, FeaturedProductsMixin, HomepageFeaturedMixin, SEOMixin):
    title = models.CharField(max_length=250, help_text="The main title of the AI learning path.")
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    level = models.CharField(max_length=50, default="beginner", help_text="e.g., Beginner, Executive, Developer")
    target_audience = models.CharField(max_length=100, blank=True, help_text="e.g., Business Leaders, Python Devs")
    
    description = models.TextField(blank=True, help_text="Short summary.")
    long_description = models.TextField(blank=True, help_text="Long marketing description.")
    
    is_published = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=True)

    class Meta:
        ordering = ['title']
        verbose_name = "AI Learning Path"
        verbose_name_plural = "AI Learning Paths"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

class AIPathWeek(models.Model):
    path = models.ForeignKey(AILearningPath, on_delete=models.CASCADE, related_name='weeks')
    week_number = models.PositiveIntegerField()
    title = models.CharField(max_length=250, help_text="e.g., 'Week 1: Fundamentals of LLMs'")
    focus = models.TextField(blank=True, help_text="The learning goal for this week.")

    class Meta:
        ordering = ['week_number']
        unique_together = ('path', 'week_number')

    def __str__(self):
        return f"{self.path.title} - Week {self.week_number}"

class AIPathDay(models.Model):
    week = models.ForeignKey(AIPathWeek, on_delete=models.CASCADE, related_name='days')
    day_number = models.PositiveSmallIntegerField(help_text="Day 1-7")
    title = models.CharField(max_length=250, help_text="e.g., 'Prompt Engineering Basics'")
    
    theory_lesson = models.TextField(blank=True, help_text="The AI concept explained. Supports Markdown.")
    practical_exercise = models.TextField(blank=True, help_text="Actionable task (e.g., writing a prompt or API call). Supports Markdown.")
    real_world_case_study = models.TextField(blank=True, help_text="How companies use this today. Supports Markdown.")
    mindset_focus = models.TextField(blank=True, help_text="A philosophical or ethical point regarding AI.")

    class Meta:
        ordering = ['day_number']
        unique_together = ('week', 'day_number')

    def __str__(self):
        return f"{self.week.path.title} - Week {self.week.week_number} Day {self.day_number}"
    

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
    
