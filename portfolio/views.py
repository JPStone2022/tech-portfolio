import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django_q.tasks import async_task, fetch
from shop.models import Product as ShopProduct # Import the Shop model
from shop.models import Purchase
from case_study.models import TechBootcamp, BootcampWeek, BootcampDay, TechSkill, ProjectFeature


def home(request):
    featured_programs = TechBootcamp.objects.filter(is_published=True).order_by('-id')[:3]
    context = {
        'featured_programs': featured_programs,
        # ... your other context variables ...
    }
    return render(request, 'portfolio/home.html', context)

@login_required
def custom_generator(request):
    """Serves the frontend UI for users to generate custom AI bootcamps."""
    # Optional: Check rate limits here too, and pass a flag to the template to disable the form if they are over the limit!
    return render(request, 'portfolio/generate.html')


def catalog(request):
    # Grab the category from the URL if it exists
    category_filter = request.GET.get('category')
    
    # Fetch all published programs
    bootcamps = TechBootcamp.objects.filter(is_published=True).order_by('?') # Randomize for a fresh look
    
    # Apply filter if a category was clicked
    if category_filter:
        bootcamps = bootcamps.filter(category=category_filter)
        
    context = {
        'bootcamps': bootcamps,
        'current_category': category_filter,
    }
    return render(request, 'portfolio/catalog.html', context)


def program_detail(request, slug):
    bootcamp = get_object_or_404(TechBootcamp, slug=slug, is_published=True)
    shop_product = ShopProduct.objects.filter(slug=slug, is_published=True).first()
    
    # Check if the user already owns this program
    is_enrolled = False
    if request.user.is_authenticated and shop_product:
        is_enrolled = Purchase.objects.filter(user=request.user, product=shop_product).exists()
    
    context = {
        'bootcamp': bootcamp,
        'shop_product': shop_product,
        'is_enrolled': is_enrolled, # Pass the ownership flag to the template
    }
    return render(request, 'portfolio/program_detail.html', context)


@login_required # Protects this route from logged-out users
def enroll_program(request, slug):
    # Security Best Practice: Only accept POST requests for actions that change the database
    if request.method == 'POST':
        shop_product = get_object_or_404(ShopProduct, slug=slug, is_published=True)
        
        # get_or_create prevents duplicate purchases if they click the button twice!
        Purchase.objects.get_or_create(user=request.user, product=shop_product)
        
        # Once purchased, send them straight to their dashboard
        return redirect('portfolio:dashboard')
        
    return redirect('portfolio:program_detail', slug=slug)



def architecture_overview(request):
    all_skills = TechSkill.objects.all()
    features = ProjectFeature.objects.prefetch_related('technology_used').all()
    key_libraries = all_skills.filter(is_key_library=True).order_by('order')
    
    # Group standard skills by category
    skills_by_category = {
        'Artificial Intelligence & LLMs': all_skills.filter(category='AI'),
        'Backend Architecture': all_skills.filter(category='BACKEND'),
        'Frontend & UI': all_skills.filter(category='FRONTEND'),
        'Database & Caching': all_skills.filter(category='DATABASE'),
        'DevOps & CI/CD': all_skills.filter(category='DEVOPS'),
    }

    # Filter out empty categories so they don't render empty boxes on the UI
    active_categories = {k: v for k, v in skills_by_category.items() if v.exists()}

    context = {
        'skills_by_category': active_categories,
        'features': features,
        'key_libraries': key_libraries,
    }
    return render(request, 'portfolio/architecture.html', context)


# --- AUTHENTICATION VIEWS ---

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Automatically log them in after sign up
            return redirect('portfolio:dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'portfolio/register.html', {'form': form})

# --- THE USER DASHBOARD ---

@login_required # This decorator bounces unauthenticated users to the login page
def dashboard(request):
    # 1. Fetch all "receipts" (Purchases) belonging to the logged-in user
    user_purchases = Purchase.objects.filter(user=request.user)
    
    # 2. Extract the product slugs from those receipts
    owned_slugs = user_purchases.values_list('product__slug', flat=True)
    
    # 3. Fetch the actual Bootcamps that match those slugs
    my_bootcamps = TechBootcamp.objects.filter(slug__in=owned_slugs)
    
    context = {
        'my_bootcamps': my_bootcamps,
    }
    return render(request, 'portfolio/dashboard.html', context)


@login_required
def study_portal(request, slug, week_num, day_num):
    # 1. Security Check: Does the user actually own this program?
    shop_product = get_object_or_404(ShopProduct, slug=slug, is_published=True)
    if not Purchase.objects.filter(user=request.user, product=shop_product).exists():
        # If they don't own it, bounce them back to the marketing page!
        return redirect('portfolio:program_detail', slug=slug)

    # 2. Fetch the Core Data
    bootcamp = get_object_or_404(TechBootcamp, slug=slug)
    
    # 3. Fetch the exact Week and Day requested in the URL
    current_week = get_object_or_404(BootcampWeek, bootcamp=bootcamp, week_number=week_num)
    current_day = get_object_or_404(BootcampDay, week=current_week, day_number=day_num)
    
    context = {
        'bootcamp': bootcamp,
        'current_week': current_week,
        'current_day': current_day,
    }
    return render(request, 'portfolio/study_portal.html', context)


# --- ASYNC GENERATION API VIEWS ---

@login_required
def trigger_generation(request):
    if request.method == 'POST':
        # 1. Check Rate Limit (e.g., Max 2 custom generations per user)
        if TechBootcamp.objects.filter(created_by=request.user).count() >= 20:
            return JsonResponse({"error": "Limit Reached. You can only generate 2 custom programs."}, status=403)
            
        data = json.loads(request.body)
        
        # 2. Dispatch to the background worker immediately!
        task_id = async_task(
            'case_study.tasks.generate_user_custom_program', 
            request.user.id, 
            data['topic'], 
            data['experience'], 
            data['skill'], 
            data['goal'], 
            data['time']
        )
        
        # 3. Tell the frontend the job has started
        return JsonResponse({"message": "Generation started!", "task_id": task_id})
    
    return JsonResponse({"error": "Invalid request method"}, status=405)

@login_required
def check_task_status(request, task_id):
    # 'fetch' gets the entire Task object (including success/fail state), not just the result
    task = fetch(task_id) 
    
    if task:
        if task.success:
            # Task finished perfectly! Return the slug.
            return JsonResponse({"status": "complete", "slug": task.result.get('slug')})
        else:
            # Task crashed! Stop the frontend from polling forever.
            return JsonResponse({"status": "failed", "error": str(task.result)})
    else:
        # Task is still in the queue / running
        return JsonResponse({"status": "processing"})