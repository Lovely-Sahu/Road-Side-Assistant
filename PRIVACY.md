# RSA — Privacy and data retention (pilot)

## What is collected

| Data | Purpose | Who can see it |
|---|---|---|
| Name, email, phone, password hash | Accounts and contact | The user; admins (never the hash) |
| Driver breakdown location (only if the driver taps "Use my location") | Matching and directions | The driver, the assigned provider while they hold the job, admins |
| Provider live location (only while a job is ACCEPTED / ON_THE_WAY / ARRIVED and the provider has switched sharing on) | Driver tracking | The driver of that job, admins |
| Provider base location (set by the provider) | Distance-based matching | Admins; used internally for ranking |
| Incident description, AI analysis, photos | Assistance and history | The driver, the assigned provider, admins |
| Status history, notifications, feedback, audit log | Operations and accountability | As applicable; audit log is admins only |
| Login attempts (email, IP, time) | Brute-force protection | Not displayed; deleted after 7 days |

## Minimisation rules built into the app

- Location is **never** invented. Missing locations are stored as empty, never as a default coordinate.
- Provider location breadcrumbs are stored at most once every 10 seconds, only for an active, accepted job. Sharing stops when service starts or the job ends.
- A provider sees the driver's phone number only while holding the job. Providers that rejected or were reassigned lose access to the request.
- Photos are stored outside the public web folder and served only after a permission check.
- The audit log never records passwords, tokens or other secrets.

## Retention (recommended for the pilot. Decide and publish your own policy.)

- Provider location breadcrumbs (`tracking` rows with `location_source='provider'`): delete 30 days after the request closes.
- Photos: delete 90 days after the request closes.
- Requests, diagnoses and status history: keep for the service-records period you choose (for example 1 year), then anonymise.
- Login attempts: automatically deleted after 7 days.

These deletions are **not** automatic in this version, apart from login attempts. Run them as an
admin task with a backup taken first.

## User rights

Provide a contact for access and deletion requests. Deactivating an account (Admin → Users) stops
access immediately and keeps service history intact. Deleting a user removes their requests through
the database cascade, so take a backup first.
