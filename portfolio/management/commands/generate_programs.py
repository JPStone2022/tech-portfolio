from django.core.management.base import BaseCommand
# Import the new Celery task, NOT the original script
from ai_concepts.tasks import generate_ai_course_background 

class Command(BaseCommand):
    help = 'Runs the Auto AI Program Generation Script asynchronously'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1, help='Number of programs to generate')
        parser.add_argument('--weeks', type=int, default=4, help='Number of weeks in the course')
        parser.add_argument('--locale', type=str, default='uk', help='Locale (uk, us, or both)')

    def handle(self, *args, **kwargs):
        limit = kwargs['limit']
        weeks = kwargs['weeks']
        locale = kwargs['locale']

        self.stdout.write(self.style.WARNING(f'Sending task to Celery Queue (Limit: {limit})...'))
        
        try:
            # The .delay() method is the secret sauce! 
            generate_ai_course_background.delay(limit=limit, weeks=weeks, locale=locale)
            
            self.stdout.write(self.style.SUCCESS('Task successfully added to the background queue! You can now continue using your terminal.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error queuing task: {e}'))