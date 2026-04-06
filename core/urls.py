from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('portfolio.urls')), # Route the homepage to the portfolio app
    path('contact/', include('contact.urls'))
]