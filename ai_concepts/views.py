from django.shortcuts import render, get_object_or_404
from .models import AILearningPath, AIPathWeek, AIPathDay

def path_list(request):
    # Only fetch courses that are marked as published
    courses = AILearningPath.objects.filter(is_published=True).order_by('id')
    return render(request, 'ai_concepts/path_list.html', {'courses': courses})

def path_detail(request, slug):
    # Fetch the specific course by its slug, or return a 404 page
    course = get_object_or_404(AILearningPath, slug=slug, is_published=True)
    
    # Fetch all the weeks related to this course
    weeks = AIPathWeek.objects.filter(path=course).order_by('week_number')
    
    # We will pass the weeks and days down to the template
    return render(request, 'ai_concepts/path_detail.html', {
        'course': course,
        'weeks': weeks
    })