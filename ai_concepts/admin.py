from django.contrib import admin
from .models import AILearningPath, AIPathWeek, AIPathDay

@admin.register(AILearningPath)
class AILearningPathAdmin(admin.ModelAdmin):
    list_display = ('title', 'level', 'is_paid', 'is_published')
    search_fields = ('title', 'target_audience')
    list_filter = ('level', 'is_paid', 'is_published')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(AIPathWeek)
class AIPathWeekAdmin(admin.ModelAdmin):
    list_display = ('path', 'week_number', 'title')
    list_filter = ('path',)
    search_fields = ('title', 'focus')

@admin.register(AIPathDay)
class AIPathDayAdmin(admin.ModelAdmin):
    list_display = ('week', 'day_number', 'title')
    list_filter = ('week__path',)
    search_fields = ('title', 'theory_lesson')