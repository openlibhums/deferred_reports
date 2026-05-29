from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from plugins.deferred_reports.models import ReportTask
from plugins.deferred_reports import email as report_email
from plugins.deferred_reports.execute import execute_report


class Command(BaseCommand):
    help = (
        'Processes any report tasks in pending state. '
        'Intended to be run regularly via cron. '
        'Tasks stuck in processing for longer than --stuck-after minutes '
        'are assumed to have crashed and are reset to pending.'
    )

    MAX_ATTEMPTS = 3

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Maximum number of reports to process per run (default: 5).',
        )
        parser.add_argument(
            '--stuck-after',
            type=int,
            default=10,
            help=(
                'Minutes a task can be in processing state before it is '
                'considered crashed and reset to pending (default: 10).'
            ),
        )

    def handle(self, *args, **options):
        stuck_after = options['stuck_after']
        cutoff = timezone.now() - timedelta(minutes=stuck_after)

        stuck = ReportTask.objects.filter(
            status=ReportTask.STATUS_PROCESSING,
            created__lt=cutoff,
        )
        if stuck.exists():
            count = stuck.count()
            stuck.update(status=ReportTask.STATUS_PENDING)
            self.stdout.write(
                f'Reset {count} task(s) stuck in processing for '
                f'>{stuck_after} minutes.',
            )

        # Mark exhausted tasks as permanently failed before picking up work.
        exhausted = ReportTask.objects.filter(
            status=ReportTask.STATUS_PENDING,
            attempt_count__gte=self.MAX_ATTEMPTS,
        )
        if exhausted.exists():
            count = exhausted.count()
            exhausted.update(status=ReportTask.STATUS_FAILED)
            self.stdout.write(
                self.style.WARNING(
                    f'Marked {count} task(s) as failed after '
                    f'{self.MAX_ATTEMPTS} attempts.',
                )
            )
            for task in ReportTask.objects.filter(
                status=ReportTask.STATUS_FAILED,
                attempt_count__gte=self.MAX_ATTEMPTS,
            ):
                report_email.send_failure_email(task)

        limit = options['limit']
        pending = ReportTask.objects.filter(
            status=ReportTask.STATUS_PENDING,
        ).order_by('created')[:limit]
        count = len(pending)

        total_pending = ReportTask.objects.filter(
            status=ReportTask.STATUS_PENDING,
        ).count()

        if not count:
            self.stdout.write('No pending report tasks.')
            return

        self.stdout.write(
            f'Found {total_pending} pending report task(s) total; '
            f'processing {count} (limit: {limit}).',
        )

        for task in pending:
            journal_label = f' [{task.journal.code}]' if task.journal else ''
            params_label = (
                ', '.join(f'{k}={v}' for k, v in task.parameters.items())
                if task.parameters else 'no parameters'
            )
            self.stdout.write(
                f'  [{task.pk}] {task.report_name}{journal_label} '
                f'requested by {task.user.email} '
                f'at {task.created.strftime("%Y-%m-%d %H:%M")} '
                f'({params_label}) [attempt {task.attempt_count + 1}/{self.MAX_ATTEMPTS}]',
            )
            execute_report(task.pk)
            task.refresh_from_db()
            if task.status == ReportTask.STATUS_COMPLETE:
                self.stdout.write(
                    self.style.SUCCESS(f'    -> complete: {task.file_path}'),
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'    -> failed (attempt {task.attempt_count}/'
                        f'{self.MAX_ATTEMPTS}): {task.error_message}'
                    ),
                )
                if task.attempt_count < self.MAX_ATTEMPTS:
                    task.status = ReportTask.STATUS_PENDING
                    task.save(update_fields=['status'])

        self.stdout.write(
            self.style.SUCCESS(f'Done. Processed {count} report task(s).'),
        )
