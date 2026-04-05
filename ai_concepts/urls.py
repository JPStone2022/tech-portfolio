from django.urls import path
from . import views

app_name = 'ai_concepts' # This is called URL namespacing, a major best practice!

urlpatterns = [
    path('', views.path_list, name='path_list'),
    path('<slug:slug>/', views.path_detail, name='path_detail'),
]