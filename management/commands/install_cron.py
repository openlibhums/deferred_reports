import os

from django.conf import settings
from django.core.management.base import BaseCommand

try:
    import crontab
except (ImportError, ModuleNotFoundError):
    crontab = None


def find_job(tab, comment):
    for job in tab:
        if job.comment == comment:
            return job
    return None


class Command(BaseCommand):
    """
    Installs cron jobs for the Deferred Reports plugin.
    """

    help = "Installs cron jobs for the Deferred Reports plugin."

    def add_arguments(self, parser):
        parser.add_argument("--action", default="")

    def handle(self, *args, **options):
        if not os.path.isfile("/usr/bin/crontab"):
            self.stdout.write(
                self.style.WARNING(
                    "WARNING: /usr/bin/crontab not found, skipping crontab config."
                )
            )
            return

        if not crontab:
            self.stdout.write(
                self.style.WARNING(
                    "WARNING: crontab module is not installed, skipping crontab config."
                )
            )
            return

        action = options.get("action")
        tab = crontab.CronTab(user=True)
        virtualenv = os.environ.get("VIRTUAL_ENV", None)

        cwd = settings.PROJECT_DIR.replace("/", "_")

        jobs = [
            {
                "name": "{}_deferred_reports_process".format(cwd),
                "time": 5,
                "task": "process_pending_reports",
                "type": "mins",
            },
            {
                "name": "{}_deferred_reports_cleanup".format(cwd),
                "time": 3,
                "task": "cleanup_old_reports",
                "type": "daily",
            },
        ]

        for job in jobs:
            current_job = find_job(tab, job["name"])

            if not current_job:
                django_command = "{0}/manage.py {1}".format(
                    settings.BASE_DIR, job["task"]
                )
                if virtualenv:
                    command = "%s/bin/python3 %s" % (virtualenv, django_command)
                else:
                    command = "%s" % (django_command)

                cron_job = tab.new(command, comment=job["name"])

                if job.get("type") == "daily":
                    cron_job.setall("0 {} * * *".format(job["time"]))
                else:
                    cron_job.minute.every(job["time"])

                self.stdout.write(
                    self.style.SUCCESS(
                        "Installed cron job: {name}".format(name=job["name"])
                    )
                )
            else:
                self.stdout.write(
                    "{name} cron job already exists.".format(name=job["name"])
                )

        if action == "test":
            self.stdout.write(tab.render())
        elif action == "quiet":
            pass
        else:
            tab.write()
