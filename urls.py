from django.urls import re_path

from plugins.deferred_reports import views

urlpatterns = [
    re_path(
        r'^$',
        views.index,
        name='deferred_reports_index',
    ),
    re_path(
        r'^configure/(?P<report_type>[\w]+)/$',
        views.configure_report,
        name='deferred_reports_configure',
    ),
    re_path(
        r'^my-reports/$',
        views.my_reports,
        name='deferred_reports_my_reports',
    ),
    re_path(
        r'^view/(?P<task_id>\d+)/$',
        views.view_report,
        name='deferred_reports_view',
    ),
    re_path(
        r'^download/(?P<task_id>\d+)/$',
        views.download_report,
        name='deferred_reports_download',
    ),
    re_path(
        r'^delete/(?P<task_id>\d+)/$',
        views.delete_report,
        name='deferred_reports_delete',
    ),
    re_path(
        r'^debug/process/$',
        views.debug_process,
        name='deferred_reports_debug_process',
    ),
]
