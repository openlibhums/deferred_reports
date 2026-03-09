from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deferred_reports', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttask',
            name='attempt_count',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
