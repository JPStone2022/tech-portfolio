from django.core.management.base import BaseCommand
# Import the master generator directly from your services folder
from portfolio.services.orchestrate_master_hybrid import run_auto_generator

class Command(BaseCommand):
    help = 'Synchronously generates tiered tech bootcamps using the Master Hybrid Engine.'

    def add_arguments(self, parser):
        # We define the exact same flags your master script expects
        parser.add_argument(
            '--topic',
            type=str,
            required=True,
            choices=['AI', 'DS', 'WEB', 'TECH'],
            help="Which topic engine to run (e.g., AI, DS, WEB, TECH)"
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1,
            help="Maximum number of personas/programs to generate"
        )
        parser.add_argument(
            '--weeks',
            type=int,
            default=4,
            help="Duration of the program in weeks"
        )
        parser.add_argument(
            '--locale',
            type=str,
            default='both',
            choices=['uk', 'us', 'both'],
            help="The target locale region for the content"
        )

    def handle(self, *args, **kwargs):
        # Extract the variables passed from the terminal
        topic = kwargs['topic']
        limit = kwargs['limit']
        weeks = kwargs['weeks']
        locale = kwargs['locale']

        self.stdout.write(self.style.WARNING(f"Initializing Master Engine for Topic: {topic} (Limit: {limit})..."))
        self.stdout.write(self.style.WARNING("Running synchronously in the main thread. Please wait..."))

        try:
            # We call the function directly (NO .delay() for Celery)
            run_auto_generator(
                topic_key=topic,
                limit=limit,
                weeks=weeks,
                locale=locale
            )
            
            self.stdout.write(self.style.SUCCESS(f"\nSUCCESS: Finished synchronous generation for {topic}!"))
            self.stdout.write(self.style.SUCCESS(f"Check your Django Admin to view the newly created records."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"A critical error occurred during generation: {e}"))

# python manage.py generate_programs --topic WEB --limit 1 --weeks 4 --locale uk