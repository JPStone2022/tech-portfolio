from django.views.generic import ListView
from .models import CuratedProduct

class CuratedProductListView(ListView):
    model = CuratedProduct
    template_name = 'products/product_list.html' # Or .html depending on your setup
    context_object_name = 'products'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Recommended Gear"
        return context