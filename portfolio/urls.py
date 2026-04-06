from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.home, name='home'),
    path('programs/', views.catalog, name='catalog'),

    # Authentication Routes
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='portfolio/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='portfolio:home'), name='logout'),
    
    # Dashboard Route
    path('dashboard/', views.dashboard, name='dashboard'),

    path('architecture/', views.architecture_overview, name='architecture'),
    path('programs/<slug:slug>/enroll/', views.enroll_program, name='enroll'),
    path('study/<slug:slug>/week/<int:week_num>/day/<int:day_num>/', views.study_portal, name='study_portal'),
    # Note: Ensure your program_detail route is BELOW these, 
    # otherwise Django might mistake 'login' for a bootcamp slug!
    path('programs/<slug:slug>/', views.program_detail, name='program_detail'),
]