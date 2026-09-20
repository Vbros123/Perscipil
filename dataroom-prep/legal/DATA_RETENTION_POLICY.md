DRAFT FOR COUNSEL REVIEW — NOT PUBLISHED

# Data Retention Policy — draft 2026-09-20
Research reports, search history, batches and monitoring events use a proposed
30-day retention window configurable through REPORT_RETENTION_DAYS. Run retention
worker daily; code existence alone is not evidence that deletion runs in production.
Saved-company entries and subscriptions remain until removed/account deleted;
monitoring stores the latest summary. Account deletion removes user-owned data and
API keys and de-identifies audit/correction control records. Security-token cleanup,
long-term control-log retention and legally required holds need final schedules.
Backups expire separately; the existing workflow retains encrypted artifacts for
seven days. Restoring an old backup must reapply subsequent account deletion requests.
Vendor retention contracts may be shorter; current permission checks reject providers
whose allowed retention is below configured report retention. Do not enable a vendor
until actual worker operation and all secondary retention locations are verified.
Counsel must approve control-log duration, deletion holds and contractual exceptions.
No indefinite retention entitlement is assumed.
