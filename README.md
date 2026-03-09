# Deferred Reports Plugin

Generates CSV reports as background tasks and notifies users by email when their download is ready. Replaces the synchronous reporting pages for reports that are too large or slow to generate within a web request.

## How it works

1. A user requests a report from the manager interface, selecting a report type and any required parameters (date range, journal, etc.).
2. A `ReportTask` record is created in the database with status `pending`.
3. The `process_pending_reports` management command (run via cron) picks up pending tasks, generates the CSV file on disk, and marks the task `complete`.
4. The user receives an email with a download link. If the report fails after three attempts, a failure email is sent instead.
5. The user can download or re-request their report from the "My Reports" page.

Reports are stored under `files/deferred_reports/` relative to `BASE_DIR`. The `cleanup_old_reports` command deletes reports and their files after 30 days (configurable).

## Installation

### 1. Install the plugin

Clone the plugin into `src/plugins/` and run the following commands:

```bash
python src/manage.py install_plugins
python src/manage.py migrate
```

`install_plugins` calls the plugin's `install()` function which registers the plugin and loads the email notification settings into the database.

### 2. Install cron jobs

The plugin ships its own `install_cron` command. Run it once after installation:

```bash
python src/manage.py install_cron --module deferred_reports
```

Or, if you are running this manually, the two jobs that need to be scheduled are:

| Command | Recommended schedule | Purpose |
|---|---|---|
| `process_pending_reports` | Every 5 minutes | Picks up and runs pending report tasks |
| `cleanup_old_reports` | Daily | Deletes reports and files older than 30 days |

Example crontab entries (adjust paths to your environment):

```cron
*/5 * * * * /path/to/venv/bin/python /path/to/src/manage.py process_pending_reports
0 3 * * *   /path/to/venv/bin/python /path/to/src/manage.py cleanup_old_reports
```

## Management commands

### `process_pending_reports`

Processes report tasks in `pending` state. Tasks stuck in `processing` for longer than `--stuck-after` minutes are assumed to have crashed and reset to `pending`. A task that fails three times is marked permanently `failed` and the user is notified.

```
python src/manage.py process_pending_reports [--limit N] [--stuck-after MINUTES]
```

| Option | Default | Description |
|---|---|---|
| `--limit` | `5` | Maximum reports to process per run |
| `--stuck-after` | `10` | Minutes before a processing task is considered crashed |

### `cleanup_old_reports`

Deletes `ReportTask` records and their CSV files older than `--days` days.

```
python src/manage.py cleanup_old_reports [--days N]
```

### `install_cron`

Installs the two cron jobs above for the current user. Requires the `python-crontab` package and `/usr/bin/crontab`. Pass `--action test` to print the crontab without writing it.

```
python src/manage.py install_cron [--action test|quiet]
```

## Available reports

Reports marked **Instant** run synchronously on request and are available immediately on the My Reports page. Reports marked **Background** are queued and processed by the cron job; the user receives an email when the file is ready.

| Report | Scope | Mode | Access | Filter | Description |
|---|---|---|---|---|---|
| Press Report | Press | Background | Editor | Date range | Submissions, publications, rejections, views, and downloads per journal. User counts are a current snapshot, not date-filtered. |
| Article Metrics | Journal | Background | Editor | Date range (metrics only) | One row per published article regardless of date. Date range filters access metrics only, not the article list. |
| Journal Usage by Month | Press | Background | Editor | Month range | Combined views and downloads per journal per month. Month range controls both the columns and the access events counted. |
| Production Times | Press | Background | Editor | Date range (assigned date) | Completed typesetting tasks assigned within the date range. Only tasks with both accepted and completed dates recorded are included. |
| Geographical Spread | Press/Journal | Background | Editor | Date range (access date) | Access events to published articles grouped by country. |
| Peer Review | Press/Journal | Background | Editor | Date range (requested date) | Completed review assignments where the review was requested within the date range. Only assignments with both acceptance and completion dates are included. |
| Article Citations | Press/Journal | Background | Editor | Year (citing work year) | Citation counts from Crossref data. Year filters by the year of the citing work; set to all-time for all years. Only articles with at least one recorded citation are included. |
| Journal Citations | Press | Instant | Editor | None | All-time citation totals per journal, aggregated from all Crossref citation records. |
| Journal Article Citations | Journal | Instant | Editor | None | All-time Crossref citation counts for articles in the selected journal that have at least one recorded citation. |
| Article Citing Works | Press | Instant | Editor | None | All Crossref citation records for a specific article. Select a journal then pick an article. |
| Article Authors | Press/Journal | Background | Editor | Date range (published date) | Authors included if they have at least one article published within the date range; all their published articles are then listed. |
| Peer Reviewers Data | Journal | Background | Editor | None | Lifetime review statistics for all reviewers with at least one assignment in the journal. |
| Author Submission Data | Journal | Background | Editor | None | All-time submission statistics for all accounts with the Author role in the journal. |
| Workflow Report | Press/Journal | Background | Editor | Month range (published date) | Lead times (submission-to-acceptance, acceptance-to-publication, submission-to-publication) for articles published within the selected months. |
| Workflow Stage Completion | Journal | Background | Editor | Month range (submitted date) | Time spent in each workflow stage for articles submitted within the selected months that have since been published. |
| Yearly Statistics | Journal | Instant | Editor | None | All years from the earliest submission on record to the current year. Each year's counts are based on submission date. |
| Articles Under Review | Journal | Instant | Editor | None | Live snapshot of open review assignments for articles currently in the Under Review stage. |
| Time to First Decision | Journal | Background | Editor | Date range (submitted date) | First editorial decision for articles submitted within the date range. |
| Crossref DOI URLs | Press/Journal | Instant | Editor | None | All published articles with a registered DOI. Includes supplementary file DOIs where available. |
| Crossref CrossCheck URLs | Press/Journal | Instant | Editor | None | All published articles with a registered DOI and a PDF galley. |
| License Report | Press | Background | Editor | Date range (published date) | Article counts grouped by licence and journal for articles published within the date range. |
| Preprints Metrics | Press | Background | Repository Manager | Date range (access date) | Views and downloads per preprint. Only preprints with at least one access in the date range appear. |
| Book Citations | Press | Instant | Staff | None | All-time citation counts per published book from Crossref BookLink data. Requires the Books plugin. |
| Book Citing Works | Press | Instant | Staff | None | All Crossref BookLink citation records for a specific book. Requires the Books plugin. |

## Email notifications

Two email templates are installed into Janeway's setting system by `install()`:

| Setting name | Group | Description |
|---|---|---|
| `deferred_reports_report_ready` | `email` | Body sent when a report is ready to download |
| `subject_deferred_reports_report_ready` | `email_subject` | Subject for the ready email |
| `deferred_reports_report_failed` | `email` | Body sent when a report has permanently failed |
| `subject_deferred_reports_report_failed` | `email_subject` | Subject for the failure email |

Templates can be customised per-journal via the Janeway manager email settings. The following context variables are available in both templates:

| Variable | Description |
|---|---|
| `task` | The `ReportTask` instance |
| `task.report_name` | Human-readable report name |
| `task.user` | The user who requested the report |
| `task.error_message` | Error detail (failure email only) |
| `download_url` | Direct download link (success email only) |
| `my_reports_url` | Link to the user's reports list |
