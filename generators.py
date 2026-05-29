import csv as csv_module
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    DateTimeField,
    DurationField,
    ExpressionWrapper,
    F,
    Func,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
    fields,
)
from django.db.models.functions import TruncMonth
from django.template.defaultfilters import strip_tags
from django.urls import reverse
from django.utils import timezone
from django.utils.text import capfirst

from core import models as core_models
from journal import models as jm
from metrics import models as mm
from production import models as pm
from review import models as rm
from review import logic as rl
from submission import models as sm

from plugins.deferred_reports.utils import (
    get_journal,
    parse_dates,
    parse_months,
    report_file_path,
    timedelta_average,
    timedelta_display,
    write_csv,
)

def generate_press_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journals = jm.Journal.objects.filter(is_remote=False).order_by('code')

    submissions_subq = sm.Article.objects.filter(
        journal=OuterRef('id'),
        date_submitted__gte=start_date,
        date_submitted__lte=end_date,
    ).annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    published_subq = sm.Article.objects.filter(
        journal=OuterRef('id'),
        date_published__gte=start_date,
        date_published__lte=end_date,
    ).annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    rejected_subq = sm.Article.objects.filter(
        journal=OuterRef('id'),
        stage=sm.STAGE_REJECTED,
        date_declined__gte=start_date,
        date_declined__lte=end_date,
    ).order_by().annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    views_subq = mm.ArticleAccess.objects.filter(
        article__journal=OuterRef('id'),
        accessed__gte=start_date,
        accessed__lte=end_date,
        type='view',
    ).order_by().annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    downloads_subq = mm.ArticleAccess.objects.filter(
        article__journal=OuterRef('id'),
        accessed__gte=start_date,
        accessed__lte=end_date,
        type='download',
    ).order_by().annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    journals = journals.annotate(
        submitted=Subquery(submissions_subq, output_field=IntegerField()),
        published=Subquery(published_subq, output_field=IntegerField()),
        rejected=Subquery(rejected_subq, output_field=IntegerField()),
        total_views=Subquery(views_subq, output_field=IntegerField()),
        total_downloads=Subquery(downloads_subq, output_field=IntegerField()),
    )

    rows = [[
        'Journal', 'Submissions', 'Published Submissions',
        'Rejected Submissions', 'Number of Users', 'Views', 'Downloads',
    ]]
    for journal in journals:
        rows.append([
            journal.name,
            journal.submitted,
            journal.published,
            journal.rejected,
            len(journal.journal_users()),
            journal.total_views,
            journal.total_downloads,
        ])

    filepath = report_file_path(task.pk, 'press_report.csv')
    write_csv(filepath, rows)
    return filepath

def generate_articles_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)

    f_editorial_delta = ExpressionWrapper(
        F('date_published') - F('date_submitted'),
        output_field=DurationField(),
    )

    articles = sm.Article.objects.filter(
        date_published__lte=timezone.now(),
        journal=journal,
    ).select_related('section').annotate(editorial_delta=f_editorial_delta)

    abstract_views = mm.ArticleAccess.objects.filter(
        article=OuterRef('id'),
        accessed__gte=start_date,
        accessed__lte=end_date,
        galley_type__isnull=True,
    ).order_by().annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    html_views = mm.ArticleAccess.objects.filter(
        article=OuterRef('id'),
        accessed__gte=start_date,
        accessed__lte=end_date,
        galley_type__in={'html', 'xml'},
        type='view',
    ).order_by().annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    pdf_views = mm.ArticleAccess.objects.filter(
        article=OuterRef('id'),
        accessed__gte=start_date,
        accessed__lte=end_date,
        galley_type='pdf',
        type='view',
    ).annotate(
        count=Func(F('id'), function='Count')
    ).values('count')

    pdf_downloads = mm.ArticleAccess.objects.filter(
        article=OuterRef('id'),
        accessed__gte=start_date,
        accessed__lte=end_date,
        galley_type='pdf',
        type='download',
    ).order_by().annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    other_downloads = mm.ArticleAccess.objects.filter(
        article=OuterRef('id'),
        accessed__gte=start_date,
        accessed__lte=end_date,
        type='download',
    ).exclude(
        galley_type__in={'pdf'},
    ).order_by().annotate(
        count=Func(F('id'), function='Count')
    ).order_by('count').values('count')

    articles = articles.annotate(
        abstract_views=Subquery(abstract_views, output_field=IntegerField()),
        html_views=Subquery(html_views, output_field=IntegerField()),
        pdf_views=Subquery(pdf_views, output_field=IntegerField()),
        pdf_downloads=Subquery(pdf_downloads, output_field=IntegerField()),
        other_downloads=Subquery(other_downloads, output_field=IntegerField()),
    )

    rows = [[
        'ID', 'Title', 'Section', 'Date Submitted', 'Date Accepted',
        'Date Published', 'Days to Publication', 'Abstract Views',
        'HTML Views', 'PDF Views', 'PDF Downloads', 'Other Downloads',
    ]]
    for article in articles:
        rows.append([
            article.pk,
            strip_tags(article.title),
            article.section.name if article.section else 'No Section',
            article.date_submitted,
            article.date_accepted,
            article.date_published,
            article.editorial_delta.days if article.editorial_delta else '',
            article.abstract_views,
            article.html_views,
            article.pdf_views,
            article.pdf_downloads,
            article.other_downloads,
        ])

    filepath = report_file_path(task.pk, 'article_metrics.csv')
    write_csv(filepath, rows)
    return filepath

def generate_articles_v2_report(task):
    """Optimised version of generate_articles_report.

    Produces byte-for-byte identical output to generate_articles_report but
    replaces the five correlated Subqueries against metrics.ArticleAccess
    with a single GROUP BY article conditional-aggregation query, merged
    into the article rows in Python.
    """
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)

    f_editorial_delta = ExpressionWrapper(
        F('date_published') - F('date_submitted'),
        output_field=DurationField(),
    )

    articles = sm.Article.objects.filter(
        date_published__lte=timezone.now(),
        journal=journal,
    ).select_related('section').annotate(editorial_delta=f_editorial_delta)

    access_counts = mm.ArticleAccess.objects.filter(
        article__journal=journal,
        accessed__gte=start_date,
        accessed__lte=end_date,
    ).values('article').annotate(
        abstract_views=Count('id', filter=Q(galley_type__isnull=True)),
        html_views=Count(
            'id', filter=Q(galley_type__in=['html', 'xml'], type='view'),
        ),
        pdf_views=Count(
            'id', filter=Q(galley_type='pdf', type='view'),
        ),
        pdf_downloads=Count(
            'id', filter=Q(galley_type='pdf', type='download'),
        ),
        other_downloads=Count(
            'id',
            filter=Q(type='download') & (
                ~Q(galley_type='pdf') | Q(galley_type__isnull=True)
            ),
        ),
    )
    counts_by_article = {row['article']: row for row in access_counts}

    rows = [[
        'ID', 'Title', 'Section', 'Date Submitted', 'Date Accepted',
        'Date Published', 'Days to Publication', 'Abstract Views',
        'HTML Views', 'PDF Views', 'PDF Downloads', 'Other Downloads',
    ]]
    for article in articles:
        counts = counts_by_article.get(article.pk, {})
        rows.append([
            article.pk,
            strip_tags(article.title),
            article.section.name if article.section else 'No Section',
            article.date_submitted,
            article.date_accepted,
            article.date_published,
            article.editorial_delta.days if article.editorial_delta else '',
            counts.get('abstract_views', 0),
            counts.get('html_views', 0),
            counts.get('pdf_views', 0),
            counts.get('pdf_downloads', 0),
            counts.get('other_downloads', 0),
        ])

    filepath = report_file_path(task.pk, 'article_metrics_v2.csv')
    write_csv(filepath, rows)
    return filepath

def generate_usage_by_month_report(task):
    date_parts = parse_months(task.parameters)
    journals = jm.Journal.objects.filter(is_remote=False, hide_from_press=False)
    journal_id_map = {j.id: j for j in journals}

    start = timezone.make_aware(timezone.datetime(
        int(date_parts['start_month_y']),
        int(date_parts['start_month_m']),
        1,
    ))
    end = timezone.make_aware(timezone.datetime(
        int(date_parts['end_month_y']),
        int(date_parts['end_month_m']),
        1,
    ) + relativedelta(months=1))

    journal_metrics = mm.ArticleAccess.objects.filter(
        article__journal__in=journals,
        type__in=['view', 'download'],
        accessed__gte=start,
        accessed__lt=end,
    ).exclude(
        galley_type__isnull=True,
    ).annotate(
        month=TruncMonth('accessed'),
    ).values(
        'article__journal', 'month',
    ).annotate(
        total=Count('id'),
    ).values(
        'article__journal', 'month', 'total',
    ).order_by('article__journal', 'month')

    dates = []
    current = start
    while current < end:
        dates.append(current)
        current += relativedelta(months=1)

    data = {}
    requested_start = start
    current_journal = None
    for row in journal_metrics:
        journal = journal_id_map.get(row['article__journal'])
        if not journal:
            continue
        data.setdefault(journal, [])
        if journal != current_journal:
            if row['month'] != requested_start:
                delta = relativedelta(
                    row['month'].date(), requested_start.date(),
                )
                months_delta = (delta.years * 12) + delta.months
                for _ in range(months_delta):
                    data[journal].append(0)
        data[journal].append(row['total'])
        current_journal = journal

    header = ['Journal'] + [d.strftime('%Y-%m') for d in dates]
    rows = [header]
    for journal, metrics in data.items():
        rows.append([journal.name] + metrics)

    filepath = report_file_path(task.pk, 'usage_by_month.csv')
    write_csv(filepath, rows)
    return filepath

def generate_production_report(task):
    start_date, end_date = parse_dates(task.parameters)
    assignments = pm.TypesetTask.objects.filter(
        completed__isnull=False,
        accepted__isnull=False,
        assigned__gte=start_date,
        assigned__lte=end_date,
    )

    rows = [[
        'Title', 'Journal', 'Typesetter', 'Assigned', 'Accepted',
        'Completed', 'Time to Acceptance', 'Time to Completion',
    ]]
    for a in assignments:
        rows.append([
            strip_tags(a.assignment.article.title),
            a.assignment.article.journal.code,
            str(a.typesetter),
            a.assigned,
            a.accepted,
            a.completed,
            (a.accepted - a.assigned).days,
            a.completed - a.accepted,
        ])

    filepath = report_file_path(task.pk, 'production_times.csv')
    write_csv(filepath, rows)
    return filepath

def generate_geo_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)

    metrics = mm.ArticleAccess.objects.filter(
        article__stage=sm.STAGE_PUBLISHED,
        accessed__gte=start_date,
        accessed__lte=end_date,
    ).values('country__name').annotate(
        country_count=Count('country'),
    )

    if journal:
        metrics = metrics.filter(article__journal=journal)

    rows = [['Country', 'Count']]
    for row in metrics:
        rows.append([row.get('country__name'), row.get('country_count')])

    filepath = report_file_path(task.pk, 'geographical_spread.csv')
    write_csv(filepath, rows)
    return filepath

def generate_review_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)

    if journal:
        articles = sm.Article.objects.filter(journal=journal)
    else:
        articles = sm.Article.objects.all()

    rows = [[
        'Reviewer', 'Article', 'Date Requested', 'Date Accepted',
        'Date Due', 'Date Complete', 'Time to Acceptance',
        'Time to Completion',
    ]]
    for article in articles:
        reviews = rm.ReviewAssignment.objects.filter(
            article=article,
            date_accepted__isnull=False,
            date_complete__isnull=False,
            date_requested__gte=start_date,
            date_requested__lte=end_date,
        )
        for review in reviews:
            rows.append([
                review.reviewer.full_name(),
                strip_tags(article.title),
                review.date_requested,
                review.date_accepted,
                review.date_due,
                review.date_complete,
                review.date_accepted - review.date_requested,
                review.date_complete - review.date_accepted,
            ])

    filepath = report_file_path(task.pk, 'peer_review.csv')
    write_csv(filepath, rows)
    return filepath

def generate_citations_report(task):
    year = task.parameters.get('year', date.today().year)
    all_time = task.parameters.get('all_time', False)
    journal = get_journal(task)

    all_articles = sm.Article.objects.filter(
        articlelink__year__isnull=False,
    ).distinct()

    if journal:
        all_articles = all_articles.filter(journal=journal)

    data = all_articles if all_time else (
        all_articles.filter(articlelink__year=year).distinct()
    )

    rows = [['Title', 'Publication Date', 'Total Citations']]
    for article in data:
        count = (
            article.citation_count if all_time
            else mm.ArticleLink.objects.filter(article=article, year=year).count()
        )
        rows.append([strip_tags(article.title), article.date_published, count])

    filepath = report_file_path(task.pk, 'article_citations.csv')
    write_csv(filepath, rows)
    return filepath

def generate_journal_citations_report(task):
    journals = jm.Journal.objects.filter(hide_from_press=False)

    rows = [['Journal', 'Total Citations']]
    for journal in journals:
        articles = sm.Article.objects.filter(
            articlelink__year__isnull=False,
            journal=journal,
        ).distinct()
        total = sum(a.citation_count for a in articles)
        rows.append([journal.name, total])

    filepath = report_file_path(task.pk, 'journal_citations.csv')
    write_csv(filepath, rows)
    return filepath

def generate_authors_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)

    accounts = core_models.Account.objects.filter(
        authors__date_published__gte=start_date,
        authors__date_published__lte=end_date,
    )
    if journal:
        accounts = accounts.filter(authors__journal=journal)

    rows = [[
        'Author Name', 'Author Email', 'Author Affiliation',
        'Article ID', 'Article Title', 'Date Published',
    ]]
    for account in accounts:
        for article in account.published_articles():
            rows.append([
                account.full_name(),
                account.email,
                account.affiliation(),
                article.id,
                strip_tags(article.title),
                article.date_published,
            ])

    filepath = report_file_path(task.pk, 'authors.csv')
    write_csv(filepath, rows)
    return filepath

def generate_reviewers_report(task):
    journal = get_journal(task)
    if not journal:
        raise ValueError('Reviewers report requires a journal.')

    reviewers = rm.ReviewAssignment.objects.filter(
        article__journal=journal,
    ).values(
        'reviewer',
        'reviewer__first_name',
        'reviewer__last_name',
    ).annotate(
        total_assignments=Count('id'),
        accepted_assignments=Count(
            'id', filter=Q(date_accepted__isnull=False),
        ),
        declined_assignments=Count(
            'id',
            filter=Q(date_declined__isnull=False, decision__isnull=True),
        ),
        withdrawn_assignments=Count(
            'id', filter=Q(decision='withdrawn'),
        ),
        completed_assignments=Count(
            'id',
            filter=Q(
                date_declined__isnull=True,
                decision__isnull=False,
                date_complete__isnull=False,
                is_complete=True,
            ),
        ),
        assignments_awaiting_response=Count(
            'id',
            filter=Q(
                decision__isnull=True,
                date_accepted__isnull=True,
                date_declined__isnull=True,
            ),
        ),
        earliest_completed_review=Min(
            'date_complete',
            filter=Q(is_complete=True, date_declined__isnull=True),
        ),
        latest_completed_review=Max(
            'date_complete',
            filter=Q(is_complete=True, date_declined__isnull=True),
        ),
        average_rating=Avg('reviewerrating__rating'),
        average_time_to_complete=Avg(
            Case(
                When(
                    date_requested__lte=F('date_complete'),
                    then=F('date_complete') - F('date_requested'),
                ),
                default=None,
                output_field=fields.DurationField(),
            ),
            filter=Q(
                date_complete__isnull=False, date_declined__isnull=True,
            ),
        ),
    )

    rows = [[
        'ID', 'First Name', 'Last Name', 'Total Requests',
        'Accepted Requests', 'Declined Requests', 'Withdrawn Requests',
        'Completed Requests', 'Requests Awaiting Response',
        'Earliest Completed Review', 'Latest Completed Review',
        'Average Time to Completion', 'Average Rating',
    ]]
    for r in reviewers:
        rows.append([
            r.get('reviewer'),
            r.get('reviewer__first_name'),
            r.get('reviewer__last_name'),
            r.get('total_assignments'),
            r.get('accepted_assignments'),
            r.get('declined_assignments'),
            r.get('withdrawn_assignments'),
            r.get('completed_assignments'),
            r.get('assignments_awaiting_response'),
            r.get('earliest_completed_review'),
            r.get('latest_completed_review'),
            r.get('average_time_to_complete'),
            r.get('average_rating'),
        ])

    filepath = report_file_path(task.pk, 'reviewers.csv')
    write_csv(filepath, rows)
    return filepath

def generate_author_data_report(task):
    journal = get_journal(task)
    if not journal:
        raise ValueError('Author data report requires a journal.')

    authors = core_models.Account.objects.filter(
        accountrole__role__slug='author',
        accountrole__journal=journal,
    ).values(
        'id', 'username', 'first_name', 'last_name', 'salutation',
    ).annotate(
        total_articles=Count(
            'authors__id',
            filter=Q(
                authors__date_submitted__isnull=False,
                authors__journal=journal,
            ),
        ),
        accepted_articles=Count(
            'authors__id',
            filter=Q(
                authors__date_submitted__isnull=False,
                authors__date_accepted__isnull=False,
                authors__journal=journal,
            ),
        ),
        declined_articles=Count(
            'authors__id',
            filter=Q(
                authors__date_submitted__isnull=False,
                authors__date_declined__isnull=False,
                authors__journal=journal,
            ),
        ),
        published_articles=Count(
            'authors__id',
            filter=Q(
                authors__date_submitted__isnull=False,
                authors__date_published__isnull=False,
                authors__journal=journal,
            ),
        ),
    )

    rows = []
    for i, author in enumerate(authors):
        if i == 0:
            rows.append([capfirst(k) for k in author.keys()])
        rows.append(list(author.values()))

    if not rows:
        rows = [['No data']]

    filepath = report_file_path(task.pk, 'author_data.csv')
    write_csv(filepath, rows)
    return filepath

def generate_workflow_report(task):
    date_parts = parse_months(task.parameters)
    journal = get_journal(task)

    article_list = sm.Article.objects.filter(
        date_published__year__gte=date_parts.get('start_month_y'),
        date_published__month__gte=date_parts.get('start_month_m'),
        date_published__year__lte=date_parts.get('end_month_y'),
        date_published__month__lte=date_parts.get('end_month_m'),
    )

    if journal:
        article_list = article_list.filter(journal=journal)

    submission_to_accept_days = []
    submission_to_publication_days = []
    accept_to_publication_days = []

    for article in article_list:
        if article.date_accepted and article.date_submitted:
            article.submission_to_accept = (
                article.date_accepted - article.date_submitted
            )
            submission_to_accept_days.append(article.submission_to_accept)
        if article.date_published and article.date_accepted:
            article.accept_to_publication = (
                article.date_published - article.date_accepted
            )
            accept_to_publication_days.append(article.accept_to_publication)
        if article.date_published and article.date_submitted:
            article.submission_to_publication = (
                article.date_published - article.date_submitted
            )
            submission_to_publication_days.append(
                article.submission_to_publication,
            )

    averages = {
        'submission_to_accept_average': timedelta_average(
            submission_to_accept_days,
        ),
        'accept_to_publication_average': timedelta_average(
            accept_to_publication_days,
        ),
        'submission_to_publication_average': timedelta_average(
            submission_to_publication_days,
        ),
    }

    rows = [
        [
            'Submission to Acceptance Average',
            'Acceptance to Publication Average',
            'Submission to Publication Average',
        ],
        [
            timedelta_display(averages['submission_to_accept_average']),
            timedelta_display(averages['accept_to_publication_average']),
            timedelta_display(averages['submission_to_publication_average']),
        ],
        [
            'ID', 'Title', 'DOI', 'Date Submitted', 'Date Accepted',
            'Date Published', 'Submission to Acceptance',
            'Acceptance to Publication', 'Submission to Publication',
        ],
    ]
    for article in article_list:
        rows.append([
            article.pk,
            strip_tags(article.title),
            article.get_doi(),
            article.date_submitted,
            article.date_accepted,
            article.date_published,
            getattr(article, 'submission_to_accept', ''),
            getattr(article, 'accept_to_publication', ''),
            getattr(article, 'submission_to_publication', ''),
        ])

    filepath = report_file_path(task.pk, 'workflow.csv')
    write_csv(filepath, rows)
    return filepath

def generate_workflow_stages_report(task):
    date_parts = parse_months(task.parameters)
    journal = get_journal(task)
    if not journal:
        raise ValueError('Workflow stages report requires a journal.')

    start = timezone.make_aware(timezone.datetime(
        int(date_parts['start_month_y']),
        int(date_parts['start_month_m']),
        1,
    ))
    end = timezone.make_aware(timezone.datetime(
        int(date_parts['end_month_y']),
        int(date_parts['end_month_m']),
        1,
    ) + relativedelta(months=1))

    articles = sm.Article.objects.filter(
        journal=journal,
        date_submitted__range=[start, end],
        date_published__isnull=False,
    )

    workflow_elements = core_models.WorkflowElement.objects.filter(
        journal=journal,
        element_name__in=core_models.WorkflowLog.objects.filter(
            article__journal=journal,
            article__date_submitted__range=[start, end],
            article__date_published__isnull=False,
        ).values('element__element_name'),
    ).order_by('order')

    element_names = [e.element_name for e in workflow_elements]

    workflow_logs = core_models.WorkflowLog.objects.filter(
        article__journal=journal,
        article__date_submitted__range=[start, end],
        article__date_published__isnull=False,
    ).select_related('article', 'element').order_by('article', 'timestamp')

    workflow_times_dict = {}
    for article in articles:
        workflow_times_dict[article.id] = {name: None for name in element_names}
        article_logs = workflow_logs.filter(article=article)
        for index, wlog in enumerate(article_logs):
            try:
                next_log = article_logs[index + 1]
                time_in = next_log.timestamp - wlog.timestamp
            except IndexError:
                time_in = article.date_published - wlog.timestamp
            workflow_times_dict[article.pk][wlog.element.element_name] = time_in

    headers = ['Article Title', 'Date Submitted'] + [
        capfirst(n) for n in element_names
    ]
    rows = [headers]
    for article in articles:
        row = [strip_tags(article.title), article.date_submitted]
        for name in element_names:
            row.append(workflow_times_dict[article.id].get(name, ''))
        rows.append(row)

    filepath = report_file_path(task.pk, 'workflow_stages.csv')
    write_csv(filepath, rows)
    return filepath

def generate_yearly_stats_report(task):
    journal = get_journal(task)
    if not journal:
        raise ValueError('Yearly stats report requires a journal.')

    earliest_year_qs = sm.Article.objects.filter(
        journal=journal,
    ).order_by('date_submitted').values('date_submitted__year').first()

    if not earliest_year_qs:
        filepath = report_file_path(task.pk, 'yearly_stats.csv')
        write_csv(filepath, [['No data']])
        return filepath

    earliest_year = earliest_year_qs['date_submitted__year']
    current_year = timezone.now().year

    rows = [[
        'Year', 'Articles Submitted', 'In Review', 'Articles Accepted',
        'Articles Rejected', 'Articles Published', 'Articles Archived',
    ]]
    for year in range(earliest_year, current_year + 1):
        stats = sm.Article.objects.filter(
            journal=journal, date_submitted__year=year,
        ).aggregate(
            articles_submitted=Count('id'),
            articles_in_review=Count(
                Case(
                    When(
                        stage__in=['Assigned', 'Under Review', 'Under Revision'],
                        then='id',
                    ),
                    default=None,
                    output_field=IntegerField(),
                ),
            ),
            articles_accepted=Count(
                Case(
                    When(date_accepted__isnull=False, then='id'),
                    default=None,
                    output_field=IntegerField(),
                ),
            ),
            articles_rejected=Count(
                Case(
                    When(date_declined__isnull=False, then='id'),
                    default=None,
                    output_field=IntegerField(),
                ),
            ),
            articles_published=Count(
                Case(
                    When(date_published__isnull=False, then='id'),
                    default=None,
                    output_field=IntegerField(),
                ),
            ),
            articles_archived=Count(
                Case(
                    When(stage='Archived', then='id'),
                    default=None,
                    output_field=IntegerField(),
                ),
            ),
        )
        rows.append([
            year,
            stats['articles_submitted'],
            stats['articles_in_review'],
            stats['articles_accepted'],
            stats['articles_rejected'],
            stats['articles_published'],
            stats['articles_archived'],
        ])

    filepath = report_file_path(task.pk, 'yearly_stats.csv')
    write_csv(filepath, rows)
    return filepath

def generate_under_review_report(task):
    journal = get_journal(task)
    if not journal:
        raise ValueError('Articles under review report requires a journal.')

    assignments = rm.ReviewAssignment.objects.filter(
        article__stage=sm.STAGE_UNDER_REVIEW,
        article__journal=journal,
    ).select_related(
        'article', 'article__journal', 'reviewer',
    ).order_by('article__title')

    rows = [[
        'Title', 'First Name', 'Last Name', 'Email Address',
        'Reviewer Decision', 'Recommendation', 'Access Code',
        'Due Date', 'Date Complete',
    ]]
    for review in assignments:
        rows.append([
            strip_tags(review.article.title),
            review.reviewer.first_name,
            review.reviewer.last_name,
            review.reviewer.email,
            review.request_decision_status(),
            review.decision,
            review.article.journal.site_url(
                path=rl.generate_access_code_url(
                    'do_review', review, review.access_code,
                ),
            ),
            review.date_due,
            review.date_complete,
        ])

    filepath = report_file_path(task.pk, 'articles_under_review.csv')
    write_csv(filepath, rows)
    return filepath

def generate_first_decision_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)
    if not journal:
        raise ValueError('Time to first decision report requires a journal.')

    articles = sm.Article.objects.filter(
        journal=journal,
        date_submitted__gte=start_date,
        date_submitted__lte=end_date,
    ).annotate(
        first_decision_date=ExpressionWrapper(
            Func(
                F('date_accepted'),
                F('date_declined'),
                F('revisionrequest__date_requested'),
                function='LEAST',
            ),
            output_field=DateTimeField(),
        ),
        decision_type=Case(
            When(
                date_accepted=F('first_decision_date'),
                then=Value('accept'),
            ),
            When(
                date_declined=F('first_decision_date'),
                then=Value('decline'),
            ),
            When(
                revisionrequest__date_requested=F('first_decision_date'),
                then=Value('revision'),
            ),
            default=Value('unknown'),
            output_field=CharField(),
        ),
    )

    rows = [[
        'ID', 'Title', 'Date Submitted', 'First Decision Date', 'Decision',
    ]]
    for article in articles:
        rows.append([
            article.pk,
            strip_tags(article.title),
            article.date_submitted,
            article.first_decision_date,
            article.decision_type,
        ])

    filepath = report_file_path(task.pk, 'time_to_first_decision.csv')
    write_csv(filepath, rows)
    return filepath

def generate_journal_citations_detail_report(task):
    journal = get_journal(task)
    if not journal:
        raise ValueError('Journal article citations report requires a journal.')

    articles = sm.Article.objects.filter(
        articlelink__year__isnull=False,
        journal=journal,
    ).distinct()

    rows = [['Title', 'Publication Date', 'Total Citations']]
    for article in articles:
        rows.append([
            strip_tags(article.title),
            article.date_published,
            article.citation_count,
        ])

    filepath = report_file_path(task.pk, 'journal_article_citations.csv')
    write_csv(filepath, rows)
    return filepath

def generate_article_citing_works_report(task):
    article_id = task.parameters.get('article_id')
    if not article_id:
        raise ValueError('Article citing works report requires an article_id.')

    article = sm.Article.objects.get(pk=article_id)

    rows = [['Title', 'Journal', 'Year', 'DOI']]
    for citing_work in article.articlelink_set.all():
        rows.append([
            citing_work.article_title,
            citing_work.journal_title,
            citing_work.year,
            citing_work.doi,
        ])

    filepath = report_file_path(task.pk, 'article_citing_works.csv')
    write_csv(filepath, rows)
    return filepath

def generate_book_citations_report(task):
    from utils import plugins
    if not plugins.check_plugin_exists('books'):
        raise ValueError('The Books plugin is not installed.')
    from plugins.books import models as book_models

    books = book_models.Book.objects.filter(date_published__lte=timezone.now())

    rows = [['Title', 'DOI', 'Publication Date', 'Citations']]
    for book in books:
        citation_count = mm.BookLink.objects.filter(
            doi=book.doi,
            object_type='book',
        ).count()
        rows.append([book.title, book.doi, book.date_published, citation_count])

    filepath = report_file_path(task.pk, 'book_citations.csv')
    write_csv(filepath, rows)
    return filepath

def generate_book_citing_works_report(task):
    from utils import plugins
    if not plugins.check_plugin_exists('books'):
        raise ValueError('The Books plugin is not installed.')
    from plugins.books import models as book_models

    book_id = task.parameters.get('book_id')
    if not book_id:
        raise ValueError('Book citing works report requires a book_id.')

    book = book_models.Book.objects.get(pk=book_id)
    links = mm.BookLink.objects.filter(doi=book.doi, object_type='book')

    rows = [['Title', 'DOI', 'ISBN (Print)', 'ISBN (Electronic)']]
    for link in links:
        rows.append([link.title, link.doi, link.isbn_print, link.isbn_electronic])

    filepath = report_file_path(task.pk, 'book_citing_works.csv')
    write_csv(filepath, rows)
    return filepath

def write_doi_tsv(filepath, journal=None, crosscheck=False):
    from identifiers import models as id_models

    identifiers = id_models.Identifier.objects.filter(
        article__isnull=False,
        article__stage=sm.STAGE_PUBLISHED,
        id_type='doi',
    )
    if journal:
        identifiers = identifiers.filter(article__journal=journal)
    identifiers = identifiers.order_by('article__journal', 'id')

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv_module.writer(f, delimiter='\t', lineterminator='\n')
        writer.writerow(['DOI', 'URL'])
        for identifier in identifiers:
            article = identifier.article
            if crosscheck and article.pdfs.exists():
                path = reverse(
                    'serve_article_pdf',
                    kwargs={
                        'identifier_type': 'id',
                        'identifier': article.id,
                    },
                )
                url = article.journal.site_url(path)
            else:
                url = article.url
            writer.writerow([identifier.identifier, url])

            if not crosscheck:
                from core import models as core_models_inner
                for supp in core_models_inner.SupplementaryFile.objects.filter(
                    file__article_id=article.pk,
                    doi__isnull=False,
                ):
                    writer.writerow([supp.doi, supp.url()])

def generate_crossref_dois_report(task):
    journal = get_journal(task)
    filepath = report_file_path(task.pk, 'crossref_doi_urls.tsv')
    write_doi_tsv(filepath, journal=journal, crosscheck=False)
    return filepath

def generate_crossref_dois_crosscheck_report(task):
    journal = get_journal(task)
    filepath = report_file_path(task.pk, 'crossref_crosscheck_urls.tsv')
    write_doi_tsv(filepath, journal=journal, crosscheck=True)
    return filepath

def generate_licenses_report(task):
    start_date, end_date = parse_dates(task.parameters)

    articles = sm.Article.objects.filter(
        date_published__lte=end_date,
        date_published__gte=start_date,
    ).values(
        'license', 'license__name', 'license__journal__code',
    ).annotate(
        lcount=Count('license'),
    ).order_by('lcount')

    rows = [['License', 'Journal', 'Count']]
    for row in articles:
        rows.append([
            row.get('license__name'),
            row.get('license__journal__code'),
            row.get('lcount'),
        ])

    filepath = report_file_path(task.pk, 'licenses.csv')
    write_csv(filepath, rows)
    return filepath

def generate_peer_review_data_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)
    if not journal:
        raise ValueError('Peer review data report requires a journal.')

    assignments = rm.ReviewAssignment.objects.filter(
        article__journal=journal,
        is_complete=True,
        date_complete__isnull=False,
        date_complete__gte=start_date,
        date_complete__lte=end_date,
    ).select_related('article', 'reviewer', 'article__license').order_by(
        'article', 'date_complete',
    )

    rows = [[
        'Article ID', 'Article Title', 'Article DOI',
        'Reviewer Name', 'Reviewer ORCID', 'Reviewer Affiliation',
        'Date Review Returned', 'Article Licence',
    ]]
    for ra in assignments:
        rows.append([
            ra.article.pk,
            strip_tags(ra.article.title),
            ra.article.get_doi() or '',
            ra.reviewer.full_name(),
            ra.reviewer.orcid or '',
            ra.reviewer.affiliation(),
            ra.date_complete,
            ra.article.license.name if ra.article.license else '',
        ])

    filepath = report_file_path(task.pk, 'peer_review_data.csv')
    write_csv(filepath, rows)
    return filepath


def generate_editor_assignment_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)
    if not journal:
        raise ValueError('Editor assignment report requires a journal.')

    assignments = rm.EditorAssignment.objects.filter(
        article__journal=journal,
        assigned__gte=start_date,
        assigned__lte=end_date,
    ).select_related('article', 'editor').order_by('article', 'assigned')

    rows = [[
        'Article ID', 'Article Title', 'Date Submitted',
        'Editor Assigned', 'Editor Name',
        'Decision', 'Date Decision Made', 'Date Author Notified',
    ]]
    for ea in assignments:
        article = ea.article
        if article.date_accepted:
            decision = 'Accept'
            decision_date = article.date_accepted
        elif article.date_declined:
            decision = 'Decline'
            decision_date = article.date_declined
        else:
            rev = rm.RevisionRequest.objects.filter(
                article=article,
            ).order_by('date_requested').first()
            if rev:
                decision = rev.get_type_display()
                decision_date = rev.date_requested
            else:
                decision = 'n/a'
                decision_date = 'n/a'
        rows.append([
            article.pk,
            strip_tags(article.title),
            article.date_submitted,
            ea.assigned,
            ea.editor.full_name(),
            decision,
            decision_date,
            decision_date,
        ])

    filepath = report_file_path(task.pk, 'editor_assignments.csv')
    write_csv(filepath, rows)
    return filepath


def generate_reviewer_status_report(task):
    start_date, end_date = parse_dates(task.parameters)
    journal = get_journal(task)
    if not journal:
        raise ValueError('Reviewer status report requires a journal.')

    rounds = rm.ReviewRound.objects.filter(
        article__journal=journal,
        date_started__gte=start_date,
        date_started__lte=end_date,
    ).select_related('article').order_by('article', 'round_number')

    rows = [[
        'Article ID', 'Article Title', 'Review Round',
        'Total Invited', 'Agreed', 'Declined', 'No Response', 'Reviews Submitted',
        'Min Response Time (days)', 'Max Response Time (days)', 'Avg Response Time (days)',
        'Min Review Time (days)', 'Max Review Time (days)', 'Avg Review Time (days)',
    ]]
    for rr in rounds:
        assignments = rr.reviewassignment_set.all()
        total = assignments.count()
        agreed = assignments.filter(date_accepted__isnull=False).count()
        declined = assignments.filter(
            date_declined__isnull=False, decision__isnull=True,
        ).count()
        no_response = assignments.filter(
            date_accepted__isnull=True,
            date_declined__isnull=True,
        ).count()
        completed = assignments.filter(
            is_complete=True, date_complete__isnull=False,
        ).count()

        response_times = [
            (ra.date_accepted - ra.date_requested).days
            for ra in assignments
            if ra.date_accepted and ra.date_requested
        ]
        completion_times = [
            (ra.date_complete - ra.date_accepted).days
            for ra in assignments
            if ra.date_complete and ra.date_accepted and ra.is_complete
        ]

        rows.append([
            rr.article.pk,
            strip_tags(rr.article.title),
            rr.round_number,
            total,
            agreed,
            declined,
            no_response,
            completed,
            min(response_times) if response_times else 0,
            max(response_times) if response_times else 0,
            round(sum(response_times) / len(response_times)) if response_times else 0,
            min(completion_times) if completion_times else 0,
            max(completion_times) if completion_times else 0,
            round(sum(completion_times) / len(completion_times)) if completion_times else 0,
        ])

    filepath = report_file_path(task.pk, 'reviewer_status.csv')
    write_csv(filepath, rows)
    return filepath


def generate_preprints_metrics_report(task):
    start_date, end_date = parse_dates(task.parameters)

    from repository import models as repository_models

    preprints = repository_models.Preprint.objects.filter(
        preprintaccess__accessed__gte=start_date,
        preprintaccess__accessed__lte=end_date,
    ).annotate(
        total_views=Count(
            'preprintaccess',
            filter=Q(
                preprintaccess__file=None,
                preprintaccess__accessed__date__gte=start_date,
                preprintaccess__accessed__date__lte=end_date,
            ),
        ),
        total_downloads=Count(
            'preprintaccess',
            filter=Q(
                preprintaccess__file__isnull=False,
                preprintaccess__accessed__date__gte=start_date,
                preprintaccess__accessed__date__lte=end_date,
            ),
        ),
    )

    rows = [['ID', 'Title', 'Date Published', 'Views', 'Downloads']]
    for preprint in preprints:
        rows.append([
            preprint.pk,
            preprint.title,
            preprint.date_published,
            preprint.total_views,
            preprint.total_downloads,
        ])

    filepath = report_file_path(task.pk, 'preprints_metrics.csv')
    write_csv(filepath, rows)
    return filepath

# ---------------------------------------------------------------------------
# Generator registry
# ---------------------------------------------------------------------------

REPORT_GENERATORS = {
    'press': generate_press_report,
    'articles': generate_articles_report,
    'articles_v2': generate_articles_v2_report,
    'usage_by_month': generate_usage_by_month_report,
    'production': generate_production_report,
    'geo': generate_geo_report,
    'review': generate_review_report,
    'citations': generate_citations_report,
    'journal_citations': generate_journal_citations_report,
    'journal_citations_detail': generate_journal_citations_detail_report,
    'article_citing_works': generate_article_citing_works_report,
    'book_citations': generate_book_citations_report,
    'book_citing_works': generate_book_citing_works_report,
    'crossref_dois': generate_crossref_dois_report,
    'crossref_dois_crosscheck': generate_crossref_dois_crosscheck_report,
    'licenses': generate_licenses_report,
    'preprints_metrics': generate_preprints_metrics_report,
    'authors': generate_authors_report,
    'reviewers': generate_reviewers_report,
    'author_data': generate_author_data_report,
    'workflow': generate_workflow_report,
    'workflow_stages': generate_workflow_stages_report,
    'yearly_stats': generate_yearly_stats_report,
    'under_review': generate_under_review_report,
    'first_decision': generate_first_decision_report,
    'peer_review_data': generate_peer_review_data_report,
    'editor_assignments': generate_editor_assignment_report,
    'reviewer_status': generate_reviewer_status_report,
}
