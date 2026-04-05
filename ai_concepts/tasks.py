import time
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

# --- NEW DUMMY TASK ---
@shared_task
def test_celery_worker(duration=5):
    """
    A simple task to prove the Celery queue is functioning.
    It simply sleeps for 'duration' seconds and returns a string.
    """
    print(f"Worker received ping. Simulating heavy lifting for {duration} seconds...")
    time.sleep(duration)
    return f"Success! Celery is alive and processed the task perfectly."