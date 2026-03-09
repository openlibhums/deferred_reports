import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from plugins.deferred_reports.models import ReportTask


class Command(BaseCommand):
    help = (
        'Deletes report tasks and their CSV files older than a given '
        'number of days (default: 30).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete reports older than this many days (default: 30).',
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timedelta(days=days)

        old_tasks = ReportTask.objects.filter(created__lt=cutoff)
        count = old_tasks.count()

        for task in old_tasks:
            if task.file_path and os.path.exists(task.file_path):
                try:
                    os.remove(task.file_path)
                except OSError as e:
                    self.stderr.write(
                        f'Could not delete {task.file_path}: {e}',
                    )

        old_tasks.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Deleted {count} report(s) older than {days} days.',
            ),
        )
