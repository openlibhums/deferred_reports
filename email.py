from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template
from django.urls import reverse

from utils import setting_handler
from utils.logger import get_logger

logger = get_logger(__name__)

def build_download_url(task):
    path = reverse(
        'deferred_reports_download',
        kwargs={'task_id': task.pk},
    )
    return f'{task.site_url.rstrip("/")}{path}'


def build_my_reports_url(task):
    path = reverse('deferred_reports_my_reports')
    return f'{task.site_url.rstrip("/")}{path}'


def send_success_email(task):
    journal = task.journal
    context = Context({
        'task': task,
        'download_url': build_download_url(task),
        'my_reports_url': build_my_reports_url(task),
    })
    subject = Template(
        setting_handler.get_setting('email_subject', 'subject_deferred_reports_report_ready', journal).value
    ).render(context)
    body = Template(
        setting_handler.get_setting('email', 'deferred_reports_report_ready', journal).value
    ).render(context)
    send_email(task.user.email, subject, body)


def send_failure_email(task):
    journal = task.journal
    context = Context({
        'task': task,
        'my_reports_url': build_my_reports_url(task),
    })
    subject = Template(
        setting_handler.get_setting('email_subject', 'subject_deferred_reports_report_failed', journal).value
    ).render(context)
    body = Template(
        setting_handler.get_setting('email', 'deferred_reports_report_failed', journal).value
    ).render(context)
    send_email(task.user.email, subject, body)


def send_email(to_address, subject, html_body):
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body='',
            to=[to_address],
        )
        email.attach_alternative(html_body, 'text/html')
        email.send(fail_silently=True)
    except Exception as e:
        logger.exception('Failed to send report email to %s: %s', to_address, e)
