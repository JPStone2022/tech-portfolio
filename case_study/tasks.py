import time
from celery import shared_task
from portfolio.services.orchestrate_master_hybrid import run_auto_generator, generate_full_tiered_package
from case_study.models import TechBootcamp
from shop.models import Purchase, Product

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

def generate_user_custom_program(user_id, topic_key, experience, skill, goal, time_commitment):
    
    persona = f"Experience: {experience}. Target Skill: {skill}. Goal: {goal}. Time: {time_commitment}."
    
    success = generate_full_tiered_package(
        client_persona=persona, 
        config_key=topic_key, 
        total_weeks=1,       
        locale_arg='uk'
    )
    
    if success:
        new_bootcamp = TechBootcamp.objects.order_by('-id').first()
        new_bootcamp.created_by_id = user_id
        new_bootcamp.is_published = False 
        new_bootcamp.save()
        
        # --- THE FIX ---
        # 1. Safely fetch OR create the Shop Product for this custom generation
        product, p_created = Product.objects.get_or_create(
            slug=new_bootcamp.slug,
            defaults={
                'title': new_bootcamp.title,
                'price': 0.00, # Custom generations are free/pre-paid
                'short_description': 'Your custom AI-generated curriculum.'
            }
        )
        
        # 2. Assign the actual Product object to the Purchase, not a slug lookup
        Purchase.objects.get_or_create(user_id=user_id, product=product)
        
        return {"status": "success", "slug": new_bootcamp.slug}
    else:
        return {"status": "failed"}
