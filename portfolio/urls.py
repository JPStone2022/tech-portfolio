from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.home, name='home'),
    path('programs/', views.catalog, name='catalog'),
    path('programs/<slug:slug>/', views.program_detail, name='program_detail'),
]