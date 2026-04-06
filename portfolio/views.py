from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from ai_concepts.models import TechBootcamp
from shop.models import Product as ShopProduct # Import the Shop model

def home(request):
    featured_programs = TechBootcamp.objects.filter(is_published=True).order_by('-id')[:3]
    context = {
        'featured_programs': featured_programs,
        # ... your other context variables ...
    }
    return render(request, 'portfolio/home.html', context)

from django.shortcuts import render
# Make sure to import your unified model from wherever it lives (e.g., case_study)
from ai_concepts.models import TechBootcamp 

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
    # 1. Fetch the content
    bootcamp = get_object_or_404(TechBootcamp, slug=slug, is_published=True)
    
    # 2. Fetch the decoupled Commerce Data using the shared slug
    # We use .first() so it safely returns None if no shop item exists, preventing crashes
    shop_product = ShopProduct.objects.filter(slug=slug, is_published=True).first()
    
    context = {
        'bootcamp': bootcamp,
        'shop_product': shop_product,
    }
    return render(request, 'portfolio/program_detail.html', context)