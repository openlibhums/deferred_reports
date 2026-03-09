from utils import plugins

# ---------------------------------------------------------------------------
# Permission level constants
# ---------------------------------------------------------------------------

PERM_EDITOR = 'editor'
PERM_STAFF = 'staff'
PERM_REPOSITORY_MANAGER = 'repository_manager'

# ---------------------------------------------------------------------------
# Report type registry
# ---------------------------------------------------------------------------

REPORT_TYPES = {
    'press': {
        'name': 'Press Report',
        'description': (
            'One row per non-remote journal. The date range filters '
            'submissions (by submitted date), publications (by published '
            'date), rejections (by declined date), and views and downloads '
            '(by access date). User counts are a current snapshot and are '
            'not date-filtered.'
        ),
        'form': 'DateRangeReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'articles': {
        'name': 'Article Metrics',
        'description': (
            'One row per published article in the journal, covering all '
            'currently published articles regardless of date. '
            'The date range filters the access metrics (views and downloads) '
            'only; it does not affect which articles are included.'
        ),
        'form': 'JournalDateReportForm',
        'needs_journal': True,
        'permission': PERM_EDITOR,
    },
    'usage_by_month': {
        'name': 'Journal Usage by Month',
        'description': (
            'Pivoted table with one row per journal and one column per '
            'calendar month. The month range determines both which months '
            'appear as columns and which access events are counted. '
            'Abstract-only page views (no galley) are excluded. '
            'Hidden and remote journals are excluded.'
        ),
        'form': 'MonthRangeReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'production': {
        'name': 'Production Times',
        'description': (
            'One row per typesetting task. The date range filters on the '
            'assignment date. Only tasks where both the accepted and '
            'completed dates are recorded are included.'
        ),
        'form': 'DateRangeReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'geo': {
        'name': 'Geographical Spread',
        'description': (
            'Access events (views and downloads) to published articles '
            'grouped by country. The date range filters the access events. '
            'Can be scoped to a single journal or run press-wide.'
        ),
        'form': 'DateRangeReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'review': {
        'name': 'Peer Review',
        'description': (
            'One row per completed review assignment. The date range filters '
            'on the date the review was requested. Only assignments where '
            'both the acceptance and completion dates are recorded are '
            'included. Can be scoped to a single journal or run press-wide.'
        ),
        'form': 'DateRangeReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'citations': {
        'name': 'Article Citations',
        'description': (
            'Citation counts from Crossref data. The year parameter filters '
            'which citation records are counted by the year of the citing '
            'work; select all-time to include citations from every year. '
            'Only articles with at least one recorded citation are included. '
            'Can be scoped to a single journal or run press-wide.'
        ),
        'form': 'YearReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'journal_citations': {
        'name': 'Journal Citations',
        'description': (
            'All-time Crossref citation totals per journal. No date '
            'filtering; covers all citation records regardless of year. '
            'One row per visible journal.'
        ),
        'form': 'ReportRequestForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
        'instant': True,
    },
    'authors': {
        'name': 'Article Authors',
        'description': (
            'One row per author per published article. The date range '
            'filters which authors are included: only those with at least '
            'one article published within the range. All published articles '
            'for each matched author are then listed, not just those within '
            'the range. Can be scoped to a single journal or run press-wide.'
        ),
        'form': 'DateRangeReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'reviewers': {
        'name': 'Peer Reviewers Data',
        'description': (
            'Lifetime review statistics per reviewer for the selected '
            'journal. No date filtering; covers all assignments on record. '
            'Only reviewers with at least one assignment in the journal '
            'are included.'
        ),
        'form': 'JournalOnlyReportForm',
        'needs_journal': True,
        'permission': PERM_EDITOR,
    },
    'author_data': {
        'name': 'Author Submission Data',
        'description': (
            'Submission statistics per author for the selected journal. '
            'No date filtering; covers all submissions on record. '
            'Only accounts with the Author role in the journal are included.'
        ),
        'form': 'JournalOnlyReportForm',
        'needs_journal': True,
        'permission': PERM_EDITOR,
    },
    'workflow': {
        'name': 'Workflow Report',
        'description': (
            'Lead-time analysis: submission-to-acceptance, '
            'acceptance-to-publication, and submission-to-publication. '
            'The month range filters on publication date; only articles '
            'published within the selected months are included. '
            'Opens with summary averages followed by a per-article '
            'breakdown. Can be scoped to a single journal or run '
            'press-wide.'
        ),
        'form': 'MonthRangeReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'workflow_stages': {
        'name': 'Workflow Stage Completion',
        'description': (
            'Time spent in each workflow stage per article. The month range '
            'filters on submission date; only articles submitted within '
            'the selected months that have since been published are '
            'included. Stage columns are dynamic, based on the workflow '
            'elements configured for the journal.'
        ),
        'form': 'MonthRangeReportForm',
        'needs_journal': True,
        'permission': PERM_EDITOR,
    },
    'yearly_stats': {
        'name': 'Yearly Statistics',
        'description': (
            'Year-by-year submission funnel for the selected journal. '
            'No date parameters; automatically covers all years from the '
            'earliest submission on record to the current year. Each '
            'year\'s counts are based on submission date.'
        ),
        'form': 'JournalOnlyReportForm',
        'needs_journal': True,
        'permission': PERM_EDITOR,
        'instant': True,
    },
    'under_review': {
        'name': 'Articles Under Review',
        'description': (
            'Live snapshot of all open review assignments for articles '
            'currently in the Under Review stage. No date filtering; '
            'reflects the current state of the journal at the time of '
            'the request.'
        ),
        'form': 'JournalOnlyReportForm',
        'needs_journal': True,
        'permission': PERM_EDITOR,
        'instant': True,
    },
    'first_decision': {
        'name': 'Time to First Decision',
        'description': (
            'First editorial decision (accept, decline, or revision request) '
            'for each article. The date range filters on submission date; '
            'only articles submitted within the range are included.'
        ),
        'form': 'DateRangeReportForm',
        'needs_journal': True,
        'permission': PERM_EDITOR,
    },
    'journal_citations_detail': {
        'name': 'Journal Article Citations',
        'description': (
            'All-time Crossref citation counts for articles in the selected '
            'journal. No date filtering; covers all citation records '
            'regardless of year. Only articles with at least one recorded '
            'citation are included.'
        ),
        'form': 'JournalOnlyReportForm',
        'needs_journal': True,
        'permission': PERM_EDITOR,
        'instant': True,
    },
    'article_citing_works': {
        'name': 'Article Citing Works',
        'description': (
            'All works recorded in Crossref data as citing a specific '
            'article. No date filtering; covers all citation records '
            'on file. Select a journal then pick an article from the list.'
        ),
        'form': 'ArticleJournalSelectForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
        'instant': True,
    },
    'book_citations': {
        'name': 'Book Citations',
        'description': (
            'All-time citation counts per published book from Crossref '
            'BookLink data, matched by DOI. No date filtering. '
            'Requires the Books plugin.'
        ),
        'form': 'ReportRequestForm',
        'needs_journal': False,
        'permission': PERM_STAFF,
        'instant': True,
    },
    'book_citing_works': {
        'name': 'Book Citing Works',
        'description': (
            'All works recorded in Crossref BookLink data as citing a '
            'specific book, matched by DOI. No date filtering. '
            'Select a book from the list. Requires the Books plugin.'
        ),
        'form': 'BookCitingWorksForm',
        'needs_journal': False,
        'permission': PERM_STAFF,
        'instant': True,
    },
    'crossref_dois': {
        'name': 'Crossref DOI URLs',
        'description': (
            'Tab-separated file mapping every registered DOI to its article '
            'URL. No date filtering; covers all published articles with a '
            'registered DOI. Includes supplementary file DOIs where '
            'available. Can be scoped to a single journal or exported '
            'press-wide.'
        ),
        'form': 'OptionalJournalReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
        'instant': True,
    },
    'crossref_dois_crosscheck': {
        'name': 'Crossref CrossCheck URLs',
        'description': (
            'Tab-separated file mapping every registered DOI to the direct '
            'URL of its full-text PDF galley, for submission to Crossref '
            'CrossCheck (iThenticate). No date filtering; covers all '
            'published articles with a registered DOI and a PDF galley. '
            'Can be scoped to a single journal or exported press-wide.'
        ),
        'form': 'OptionalJournalReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
        'instant': True,
    },
    'licenses': {
        'name': 'License Report',
        'description': (
            'Article counts grouped by licence and journal. The date range '
            'filters on publication date; only articles published within '
            'the range are counted.'
        ),
        'form': 'DateRangeReportForm',
        'needs_journal': False,
        'permission': PERM_EDITOR,
    },
    'preprints_metrics': {
        'name': 'Preprints Metrics',
        'description': (
            'Views and downloads per preprint. The date range filters the '
            'access events; only preprints with at least one access in '
            'the range appear in the report. Views are page-level accesses '
            '(no file); downloads are file-level accesses. '
            'Requires the repository to be active.'
        ),
        'form': 'DateRangeReportForm',
        'needs_journal': False,
        'permission': PERM_REPOSITORY_MANAGER,
    },
}

# ---------------------------------------------------------------------------
# Parameter display labels (used when rendering report parameters in the UI)
# ---------------------------------------------------------------------------

PARAMETER_LABELS = {
    'start_date': 'From',
    'end_date': 'To',
    'start_month': 'From',
    'end_month': 'To',
    'year': 'Year',
    'all_time': 'All time',
    'article_id': 'Article ID',
    'book_id': 'Book ID',
}

# ---------------------------------------------------------------------------
# File storage
# ---------------------------------------------------------------------------

import os
from django.conf import settings

REPORTS_DIR = os.path.join(settings.BASE_DIR, 'files', 'deferred_reports')

# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------

PLUGIN_NAME = 'deferred_reports'
DESCRIPTION = (
    'Generates reports as background tasks and notifies users by email '
    'when their CSV download is ready.'
)
AUTHOR = 'Andy Byers'
VERSION = '1.0'
SHORT_NAME = 'deferred_reports'
DISPLAY_NAME = 'Deferred Reports'
MANAGER_URL = 'deferred_reports_index'
JANEWAY_VERSION = "1.5.1"


class ReportingAsyncPlugin(plugins.Plugin):
    plugin_name = PLUGIN_NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    author = AUTHOR
    short_name = SHORT_NAME
    version = VERSION
    janeway_version = JANEWAY_VERSION
    manager_url = MANAGER_URL


def install():
    from utils.install import update_settings
    ReportingAsyncPlugin.install()
    update_settings(file_path='plugins/deferred_reports/install/settings.json')


def hook_registry():
    return {}
