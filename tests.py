import csv
import os

from django.test import TestCase
from django.utils import timezone

from metrics import models as mm
from utils.testing import helpers

from plugins.deferred_reports.execute import InstantReportContext
from plugins.deferred_reports.generators import (
    generate_articles_report,
    generate_articles_v2_report,
)


def read_report_rows(filepath):
    with open(filepath, newline='', encoding='utf-8') as f:
        return list(csv.reader(f))


def make_task(journal, pk, start_date, end_date):
    return InstantReportContext(
        parameters={
            'journal_id': journal.pk,
            'start_date': start_date,
            'end_date': end_date,
        },
        journal=journal,
        pk=pk,
    )


def create_access(article, access_type, galley_type, accessed):
    return mm.ArticleAccess.objects.create(
        article=article,
        type=access_type,
        galley_type=galley_type,
        accessed=accessed,
    )


class ArticlesV2ReportTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.press = helpers.create_press()
        cls.journal, _ = helpers.create_journals()

        now = timezone.now()
        cls.start_date = '2020-01-01'
        cls.end_date = '2030-12-31'
        cls.accessed = timezone.make_aware(
            timezone.datetime(2024, 6, 1, 12, 0, 0),
        )

        cls.article = helpers.create_article(cls.journal)
        cls.article.date_submitted = now
        cls.article.date_accepted = now
        cls.article.date_published = now
        cls.article.stage = 'Published'
        cls.article.save()

        cls.empty_article = helpers.create_article(cls.journal)
        cls.empty_article.date_submitted = now
        cls.empty_article.date_accepted = now
        cls.empty_article.date_published = now
        cls.empty_article.stage = 'Published'
        cls.empty_article.save()

        # A full spread of access events on the first article, covering
        # every metric category plus the NULL-galley download edge case.
        create_access(cls.article, 'view', None, cls.accessed)
        create_access(cls.article, 'view', 'html', cls.accessed)
        create_access(cls.article, 'view', 'xml', cls.accessed)
        create_access(cls.article, 'view', 'pdf', cls.accessed)
        create_access(cls.article, 'download', 'pdf', cls.accessed)
        create_access(cls.article, 'download', 'epub', cls.accessed)
        create_access(cls.article, 'download', None, cls.accessed)

    def test_v2_output_matches_original_exactly(self):
        original_task = make_task(
            self.journal, 'orig', self.start_date, self.end_date,
        )
        v2_task = make_task(
            self.journal, 'v2', self.start_date, self.end_date,
        )

        original_path = generate_articles_report(original_task)
        v2_path = generate_articles_v2_report(v2_task)

        self.assertEqual(
            read_report_rows(original_path),
            read_report_rows(v2_path),
        )

    def test_v2_counts_for_article_with_known_access(self):
        v2_task = make_task(
            self.journal, 'v2counts', self.start_date, self.end_date,
        )
        rows = read_report_rows(generate_articles_v2_report(v2_task))

        header = rows[0]
        data = {row[0]: row for row in rows[1:]}
        article_row = data[str(self.article.pk)]

        def col(name):
            return article_row[header.index(name)]

        # Abstract Views counts every NULL-galley access regardless of type,
        # so both the abstract page view and the NULL-galley download match.
        self.assertEqual(col('Abstract Views'), '2')
        # html and xml views are both bucketed into HTML Views by the report.
        self.assertEqual(col('HTML Views'), '2')
        self.assertEqual(col('PDF Views'), '1')
        self.assertEqual(col('PDF Downloads'), '1')
        # epub download + NULL-galley download both count as other downloads.
        self.assertEqual(col('Other Downloads'), '2')

    def test_v2_empty_article_matches_original(self):
        original_task = make_task(
            self.journal, 'origempty', self.start_date, self.end_date,
        )
        v2_task = make_task(
            self.journal, 'v2empty', self.start_date, self.end_date,
        )

        original_rows = read_report_rows(generate_articles_report(original_task))
        v2_rows = read_report_rows(generate_articles_v2_report(v2_task))

        original_data = {row[0]: row for row in original_rows[1:]}
        v2_data = {row[0]: row for row in v2_rows[1:]}

        key = str(self.empty_article.pk)
        self.assertEqual(original_data[key], v2_data[key])

    def test_v2_query_count_is_constant_across_articles(self):
        # v2 issues a fixed three queries regardless of article count:
        # the journal lookup, the single access aggregation, and the
        # article fetch. The access aggregation is one flat GROUP BY scan
        # rather than five correlated subqueries per article.
        v2_task = make_task(
            self.journal, 'v2queries', self.start_date, self.end_date,
        )
        with self.assertNumQueries(3):
            generate_articles_v2_report(v2_task)

        # Adding more articles must not increase the v2 query count.
        now = timezone.now()
        for _ in range(5):
            extra = helpers.create_article(self.journal)
            extra.date_submitted = now
            extra.date_published = now
            extra.stage = 'Published'
            extra.save()
            create_access(extra, 'view', 'pdf', self.accessed)

        v2_task_more = make_task(
            self.journal, 'v2queriesmore', self.start_date, self.end_date,
        )
        with self.assertNumQueries(3):
            generate_articles_v2_report(v2_task_more)
