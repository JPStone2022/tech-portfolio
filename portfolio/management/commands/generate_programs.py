from django.core.management.base import BaseCommand
from portfolio.services.orchestrate_ai_learning_generation_regional import run_auto_generator

class Command(BaseCommand):
    help = 'Runs the Auto AI Program Generation Script'

    # 1. Define the arguments you want to accept in the terminal
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1, help='Number of programs to generate')
        parser.add_argument('--weeks', type=int, default=4, help='Number of weeks in the course')
        parser.add_argument('--locale', type=str, default='uk', help='Locale (uk, us, or both)')

    def handle(self, *args, **kwargs):
        # 2. Extract the variables passed from the terminal
        limit = kwargs['limit']
        weeks = kwargs['weeks']
        locale = kwargs['locale']

        self.stdout.write(self.style.WARNING(f'Starting AI Generation (Limit: {limit}, Weeks: {weeks}, Locale: {locale})...'))
        
        try:
            # 3. Call the main function, passing in the required arguments!
            run_auto_generator(limit=limit, weeks=weeks, locale=locale)
            
            self.stdout.write(self.style.SUCCESS('Successfully completed AI generation!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during generation: {e}'))