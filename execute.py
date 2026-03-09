from dataclasses import dataclass, field
from typing import Optional

from django.utils import timezone

from utils.logger import get_logger

from plugins.deferred_reports import email as report_email

logger = get_logger(__name__)


@dataclass
class InstantReportContext:
    """
    A lightweight substitute for ReportTask used when running a report
    synchronously. Generators access task.parameters, task.journal, and
    task.pk — this dataclass provides exactly those attributes.

    Note: any generator that accesses other ReportTask attributes will
    raise an AttributeError on the instant path.
    """
    parameters: dict = field(default_factory=dict)
    journal: Optional[object] = None
    pk: str = 'instant'


def execute_report(task_id):
    """Execute a report task, updating attempt_count and status."""
    from plugins.deferred_reports.models import ReportTask
    from plugins.deferred_reports.generators import REPORT_GENERATORS

    task = None
    try:
        task = ReportTask.objects.get(pk=task_id)
        task.status = ReportTask.STATUS_PROCESSING
        task.attempt_count += 1
        task.save(update_fields=['status', 'attempt_count'])

        generator = REPORT_GENERATORS.get(task.report_type)
        if not generator:
            raise ValueError(f'Unknown report type: {task.report_type}')

        filepath = generator(task)

        task.status = ReportTask.STATUS_COMPLETE
        task.file_path = filepath
        task.completed = timezone.now()
        task.save(update_fields=['status', 'file_path', 'completed'])

        report_email.send_success_email(task)

    except Exception as e:
        logger.exception('Report task %s failed: %s', task_id, e)
        if task is not None:
            try:
                task.error_message = str(e)
                task.completed = timezone.now()
                task.save(update_fields=['error_message', 'completed'])
            except Exception as e:
                logger.exception('Could not update failed task %s: %s', task_id, e)
