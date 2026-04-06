import json
from django.shortcuts import render
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from .forms import ContactForm

def contact_view(request):
    # 1. HANDLE THE AJAX POST REQUEST
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            form = ContactForm(data)
            
            # Honeypot Check: If a bot filled out 'website', pretend it was successful
            if data.get('website'):
                return JsonResponse({"success": True})
                
            if form.is_valid():
                submission = form.save(commit=False)
                submission.ip_address = request.META.get('REMOTE_ADDR')
                submission.save()
                
                # Try to send email notification
                try:
                    send_mail(
                        subject=f"Portfolio Lead: {submission.subject}",
                        message=f"From: {submission.name} ({submission.email})\n\n{submission.message}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.ADMIN_EMAIL], # Ensure this is set in settings.py!
                        fail_silently=True,
                    )
                except Exception:
                    pass # Email failed, but we still saved it to the DB!
                
                return JsonResponse({"success": True})
            else:
                return JsonResponse({"success": False, "errors": form.errors}, status=422)
                
        except Exception as e:
            return JsonResponse({"success": False, "message": "Server error."}, status=500)

    # 2. RENDER THE NORMAL WEBPAGE
    form = ContactForm()
    return render(request, 'contact/contact.html', {'form': form})