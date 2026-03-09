from django import forms
from django.forms import ModelChoiceField

from journal import models


class JournalChoiceField(ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class DateInput(forms.DateInput):
    input_type = 'date'


class MonthInput(forms.DateInput):
    input_type = 'month'


class ReportRequestForm(forms.Form):
    """Base form for all report requests. Subclassed per report type."""
    report_type = forms.CharField(widget=forms.HiddenInput())


class DateRangeReportForm(ReportRequestForm):
    start_date = forms.DateField(widget=DateInput())
    end_date = forms.DateField(widget=DateInput())


class MonthRangeReportForm(ReportRequestForm):
    start_month = forms.DateField(widget=MonthInput())
    end_month = forms.DateField(widget=MonthInput())


class JournalDateReportForm(ReportRequestForm):
    journal = JournalChoiceField(
        queryset=models.Journal.objects.all().order_by('code'),
        label='Select a Journal',
    )
    start_date = forms.DateField(widget=DateInput())
    end_date = forms.DateField(widget=DateInput())


class JournalOnlyReportForm(ReportRequestForm):
    """For reports that only need a journal (uses request.journal)."""
    pass


class YearReportForm(ReportRequestForm):
    year = forms.IntegerField()
    all_time = forms.BooleanField(
        required=False,
        help_text='Ignores the year value.',
    )


class OptionalJournalReportForm(ReportRequestForm):
    """For reports where a journal filter is optional."""
    journal = JournalChoiceField(
        queryset=models.Journal.objects.all().order_by('code'),
        label='Filter by Journal (optional)',
        required=False,
        empty_label='All Journals',
    )


class ArticleJournalSelectForm(ReportRequestForm):
    """Stage 1 for article_citing_works: pick a journal."""
    journal = JournalChoiceField(
        queryset=models.Journal.objects.all().order_by('code'),
        label='Select a Journal',
    )


class BookCitingWorksForm(ReportRequestForm):
    """No extra fields — books are listed in a table for selection."""
    pass
