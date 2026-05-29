from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('journal', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportTask',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('report_type', models.CharField(max_length=50)),
                ('report_name', models.CharField(max_length=255)),
                ('parameters', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('processing', 'Processing'),
                        ('complete', 'Complete'),
                        ('failed', 'Failed'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('created', models.DateTimeField(
                    default=django.utils.timezone.now,
                )),
                ('completed', models.DateTimeField(
                    blank=True, null=True,
                )),
                ('file_path', models.CharField(
                    blank=True, default='', max_length=500,
                )),
                ('error_message', models.TextField(
                    blank=True, default='',
                )),
                ('site_url', models.CharField(
                    blank=True,
                    default='',
                    help_text='Base site URL captured at request time for email links.',
                    max_length=500,
                )),
                ('journal', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='journal.journal',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='report_tasks',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created'],
            },
        ),
    ]
