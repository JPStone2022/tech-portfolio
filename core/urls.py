from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('courses/', include('ai_concepts.urls')),
    path('', include('portfolio.urls')), # Route the homepage to the portfolio app
]