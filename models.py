from django.db import models
from django.utils import timezone


class ReportTask(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETE = 'complete'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_FAILED, 'Failed'),
    )

    user = models.ForeignKey(
        'core.Account',
        on_delete=models.CASCADE,
        related_name='report_tasks',
    )
    journal = models.ForeignKey(
        'journal.Journal',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    report_type = models.CharField(max_length=50)
    report_name = models.CharField(max_length=255)
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created = models.DateTimeField(default=timezone.now)
    completed = models.DateTimeField(null=True, blank=True)
    file_path = models.CharField(max_length=500, blank=True, default='')
    error_message = models.TextField(blank=True, default='')
    site_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Base site URL captured at request time for email links.',
    )

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f'{self.report_name} ({self.status})'

    @property
    def is_downloadable(self):
        import os
        return (
            self.status == self.STATUS_COMPLETE
            and self.file_path
            and os.path.exists(self.file_path)
        )
