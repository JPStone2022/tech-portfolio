from celery import shared_task
from portfolio.services.orchestrate_ai_learning_generation_regional import run_auto_generator

@shared_task
def generate_ai_course_background(limit=1, weeks=4, locale='uk'):
    """
    This function will be picked up by the Celery worker and executed 
    in the background, freeing up the main Django server thread.
    """
    run_auto_generator(limit=limit, weeks=weeks, locale=locale)
    return f"Successfully generated {limit} courses in the background!"