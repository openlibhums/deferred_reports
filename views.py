import csv as csv_module
import os
from datetime import date

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.template.defaultfilters import strip_tags
from django.utils import timezone

from submission import models as sm
from security.decorators import editor_user_required
from utils import plugins

from plugins.deferred_reports import forms
from plugins.deferred_reports.models import ReportTask
from plugins.deferred_reports.plugin_settings import REPORT_TYPES
from plugins.deferred_reports.utils import (
    form_data_to_parameters,
    get_display_parameters,
    get_download_filename,
    queue_task,
    user_has_report_permission,
)


def check_permission(request, report_type):
    """Raise Http404 if the user lacks permission for this report type."""
    if not user_has_report_permission(request, report_type):
        raise Http404


def handle_queue(request, report_type, info, parameters):
    """Queue or run a report and redirect with an appropriate message."""
    queue_task(request, report_type, info, parameters)
    if info.get('instant'):
        messages.success(request, f'"{info["name"]}" is ready.')
    else:
        messages.success(
            request,
            f'"{info["name"]}" has been queued. '
            f'You will receive an email when your CSV is ready.',
        )
    return redirect(reverse('deferred_reports_my_reports'))


@editor_user_required
def index(request):
    """Lists all available report types."""
    pending_count = ReportTask.objects.filter(
        user=request.user,
        status__in=[ReportTask.STATUS_PENDING, ReportTask.STATUS_PROCESSING],
    ).count()

    visible_reports = {
        rt: info for rt, info in REPORT_TYPES.items()
        if user_has_report_permission(request, rt)
    }

    context = {
        'report_types': visible_reports,
        'pending_count': pending_count,
    }
    return render(request, 'deferred_reports/index.html', context)


@editor_user_required
def configure_report(request, report_type):
    """Interstitial page: shows the parameter form for a single report type."""
    if report_type not in REPORT_TYPES:
        raise Http404

    check_permission(request, report_type)
    info = REPORT_TYPES[report_type]

    if report_type == 'article_citing_works':
        return configure_article_citing_works(request, info)

    if report_type == 'book_citing_works':
        return configure_book_citing_works(request, info)

    form_class = getattr(forms, info['form'])

    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            parameters = form_data_to_parameters(form.cleaned_data)
            return handle_queue(request, report_type, info, parameters)
    else:
        initial = {'report_type': report_type}
        if info['form'] == 'DateRangeReportForm':
            d = date.today()
            initial['start_date'] = date(d.year, d.month, 1)
            initial['end_date'] = d
        elif info['form'] == 'MonthRangeReportForm':
            now = timezone.now()
            initial['start_month'] = f'{now.year}-01-01'
            initial['end_month'] = now.strftime('%Y-%m-01')
        form = form_class(initial=initial)

    context = {
        'report_type': report_type,
        'info': info,
        'form': form,
    }
    return render(request, 'deferred_reports/configure_report.html', context)


def configure_article_citing_works(request, info):
    """
    Two-step flow:
    Stage 1 (GET or POST without article_id): show journal picker.
    Stage 2 (POST with journal_id, no article_id): show articles table.
    Stage 3 (POST with journal_id + article_id): queue the report.
    """
    report_type = 'article_citing_works'
    journal = None
    articles = None
    journal_form = forms.ArticleJournalSelectForm(
        initial={'report_type': report_type},
    )

    if request.method == 'POST':
        article_id = request.POST.get('article_id')
        journal_id = request.POST.get('journal_id')

        if article_id and journal_id:
            # Stage 3: run or queue the report
            parameters = {'journal_id': int(journal_id), 'article_id': int(article_id)}
            return handle_queue(request, report_type, info, parameters)

        # Stage 2: journal submitted, load articles table
        journal_form = forms.ArticleJournalSelectForm(
            request.POST,
        )
        if journal_form.is_valid():
            journal = journal_form.cleaned_data['journal']
            articles = sm.Article.objects.filter(
                journal=journal,
            ).order_by('title').values('id', 'title')

    context = {
        'report_type': report_type,
        'info': info,
        'journal_form': journal_form,
        'journal': journal,
        'articles': [
            {'id': a['id'], 'title': strip_tags(a['title'])}
            for a in articles
        ] if articles is not None else None,
    }
    return render(
        request,
        'deferred_reports/configure_article_citing_works.html',
        context,
    )


def configure_book_citing_works(request, info):
    """
    Two-step flow:
    Stage 1 (GET): show all books in a table.
    Stage 2 (POST with book_id): queue the report.
    """
    report_type = 'book_citing_works'

    if not plugins.check_plugin_exists('books'):
        messages.error(request, 'The Books plugin is not installed.')
        return redirect(reverse('deferred_reports_index'))

    from plugins.books import models as book_models

    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        if book_id:
            parameters = {'book_id': int(book_id)}
            return handle_queue(request, report_type, info, parameters)

    books = book_models.Book.objects.filter(
        date_published__lte=timezone.now(),
    ).order_by('title')

    context = {
        'report_type': report_type,
        'info': info,
        'books': books,
    }
    return render(
        request,
        'deferred_reports/configure_book_citing_works.html',
        context,
    )


@editor_user_required
def my_reports(request):
    """List the current user's report tasks with status and download links."""
    tasks = ReportTask.objects.filter(user=request.user)
    context = {
        'tasks': tasks,
    }
    return render(request, 'deferred_reports/my_reports.html', context)


@editor_user_required
def view_report(request, task_id):
    """Render a completed report as an HTML table in the browser."""
    task = get_object_or_404(ReportTask, pk=task_id, user=request.user)
    check_permission(request, task.report_type)

    if not task.is_downloadable:
        raise Http404('Report is not available.')

    with open(task.file_path, newline='', encoding='utf-8') as f:
        reader = csv_module.reader(f)
        rows = list(reader)

    headers = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []

    display_parameters = get_display_parameters(task)

    context = {
        'task': task,
        'headers': headers,
        'rows': data_rows,
        'display_parameters': display_parameters,
    }
    return render(request, 'deferred_reports/view_report.html', context)


@editor_user_required
def download_report(request, task_id):
    """Serve the generated CSV file for a completed report task."""
    task = get_object_or_404(ReportTask, pk=task_id, user=request.user)
    check_permission(request, task.report_type)

    if not task.is_downloadable:
        raise Http404('Report is not available for download.')

    return FileResponse(
        open(task.file_path, 'rb'),
        as_attachment=True,
        filename=get_download_filename(task.file_path),
        content_type='text/csv',
    )


@staff_member_required
def debug_process(request):
    """Staff-only: run process_pending_reports in-process for debugging."""
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    call_command('process_pending_reports', stdout=out, stderr=out)
    output = out.getvalue()

    messages.info(request, f'process_pending_reports output: {output}')
    return redirect(reverse('deferred_reports_my_reports'))


@editor_user_required
def delete_report(request, task_id):
    """Delete a report task and its file."""
    task = get_object_or_404(ReportTask, pk=task_id, user=request.user)
    check_permission(request, task.report_type)

    if task.file_path and os.path.exists(task.file_path):
        os.remove(task.file_path)

    task.delete()
    messages.success(request, 'Report deleted.')
    return redirect(reverse('deferred_reports_my_reports'))
