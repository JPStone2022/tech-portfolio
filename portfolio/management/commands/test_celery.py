from django.core.management.base import BaseCommand
from ai_concepts.tasks import test_celery_worker 

class Command(BaseCommand):
    help = 'Sends a dummy ping to test the Celery Redis queue'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Sending test ping to Celery Queue...'))
        
        try:
            # The .delay() method pushes it to Redis
            test_celery_worker.delay(5) 
            
            self.stdout.write(self.style.SUCCESS('Ping successfully added to the background queue!'))
            self.stdout.write(self.style.SUCCESS('Run: sudo journalctl -u celery -f (to watch it process)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error queuing task: {e}'))