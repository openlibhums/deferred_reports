import csv
import os
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from journal import models as jm

from plugins.deferred_reports.plugin_settings import (
    PARAMETER_LABELS,
    PERM_EDITOR,
    PERM_REPOSITORY_MANAGER,
    PERM_STAFF,
    REPORT_TYPES,
    REPORTS_DIR,
)


def user_has_report_permission(request, report_type):
    """Return True if the current user may access the given report type."""
    info = REPORT_TYPES.get(report_type, {})
    permission = info.get('permission', PERM_EDITOR)

    if permission == PERM_STAFF:
        return request.user.is_staff

    if permission == PERM_REPOSITORY_MANAGER:
        if not request.repository:
            return False
        return (
            request.user.is_staff
            or request.user in request.repository.managers.all()
        )

    # PERM_EDITOR — already enforced by @editor_user_required on the view
    return True


def ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def report_file_path(task_id, filename):
    ensure_reports_dir()
    return os.path.join(REPORTS_DIR, f'{task_id}_{filename}')


def write_csv(filepath, rows):
    """Write rows (list of lists/tuples) to a CSV file."""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)


def parse_dates(params):
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    if not start_date:
        d = date.today()
        start_date = date(d.year, d.month, 1).isoformat()
    if not end_date:
        d = date.today()
        next_month = date(d.year, d.month, 1) + relativedelta(months=1)
        end_date = (next_month - timedelta(days=1)).isoformat()
    return start_date, end_date


def parse_months(params):
    start_month = params.get('start_month', '')
    end_month = params.get('end_month', '')

    now = timezone.now()
    if not start_month:
        start_month = f'{now.year}-01'
    if not end_month:
        end_month = f'{now.year}-{now.strftime("%m")}'

    # Handle full date strings like "2024-01-01" -> "2024-01"
    if len(start_month) > 7:
        start_month = start_month[:7]
    if len(end_month) > 7:
        end_month = end_month[:7]

    start_y, start_m = start_month.split('-')
    end_y, end_m = end_month.split('-')

    return {
        'start_month_m': start_m,
        'start_month_y': start_y,
        'end_month_m': end_m,
        'end_month_y': end_y,
        'start_unsplit': start_month,
        'end_unsplit': end_month,
    }


def get_journal(task):
    journal_id = task.parameters.get('journal_id')
    if journal_id:
        try:
            return jm.Journal.objects.get(pk=journal_id)
        except jm.Journal.DoesNotExist:
            raise ValueError(f'Journal with ID {journal_id} no longer exists.')
    return task.journal


def queue_task(request, report_type, info, parameters):
    """Create a ReportTask and run it immediately if marked instant."""
    from plugins.deferred_reports.models import ReportTask

    task = ReportTask.objects.create(
        user=request.user,
        journal=getattr(request, 'journal', None),
        report_type=report_type,
        report_name=info['name'],
        parameters=parameters,
        site_url=request.build_absolute_uri('/').rstrip('/'),
    )

    if info.get('instant'):
        from plugins.deferred_reports.execute import execute_report
        execute_report(task.pk)

    return task


def form_data_to_parameters(cleaned_data):
    """Serialise form cleaned_data to a JSON-safe parameters dict."""
    parameters = {}
    for key, value in cleaned_data.items():
        if key == 'report_type':
            continue
        if key == 'journal':
            parameters['journal_id'] = value.pk if value else None
            continue
        if hasattr(value, 'isoformat'):
            parameters[key] = value.isoformat()
        else:
            parameters[key] = value
    return parameters


def get_display_parameters(task):
    """Return a list of (label, value) pairs for display, excluding journal_id."""
    return [
        (PARAMETER_LABELS.get(k, k.replace('_', ' ').title()), v)
        for k, v in (task.parameters or {}).items()
        if k != 'journal_id'
    ]


def get_download_filename(file_path):
    """Derive a user-facing download filename from the stored file path."""
    filename = os.path.basename(file_path)
    if '_' in filename:
        filename = filename.split('_', 1)[1]
    return filename


def timedelta_display(td):
    if not td:
        return ''
    total_seconds = int(td.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    return f'{days} days {hours} hours'


def timedelta_average(timedeltas):
    if not timedeltas:
        return timedelta(0)
    return sum(timedeltas, timedelta(0)) / len(timedeltas)
