from django.contrib import admin
from .models import TechSkill, ProjectFeature
from .models import  TechBootcamp, BootcampWeek, BootcampDay

@admin.register(TechBootcamp)
class TechBootcampAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'level', 'is_published') # Added 'category'
    list_filter = ('category', 'is_published', 'level')           # Added 'category'
    prepopulated_fields = {'slug': ('title',)}

@admin.register(BootcampWeek)
class BootcampWeekAdmin(admin.ModelAdmin):
    list_display = ('bootcamp', 'week_number', 'title')
    list_filter = ('bootcamp',)
    search_fields = ('title', 'focus')

@admin.register(BootcampDay)
class BootcampDayAdmin(admin.ModelAdmin):
    list_display = ('week', 'day_number', 'title')
    list_filter = ('week__bootcamp',)
    search_fields = ('title', 'theory_lesson')


@admin.register(TechSkill)
class TechSkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_key_library', 'order')
    list_filter = ('category', 'is_key_library')
    list_editable = ('order', 'is_key_library')
    search_fields = ('name', 'description')

@admin.register(ProjectFeature)
class ProjectFeatureAdmin(admin.ModelAdmin):
    list_display = ('title', 'order')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('technology_used',)
    list_editable = ('order',)