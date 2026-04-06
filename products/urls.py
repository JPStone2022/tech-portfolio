from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('products/', views.CuratedProductListView.as_view(), name='product_list'),
]