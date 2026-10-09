# Matoshree Cyber / CSC Center

A Django application for a local CSC/cyber center: public service information, customer accounts, service applications, document uploads, appointments, manual UPI/cash payment verification, receipts, notifications, admin operations, reports, government schemes, jobs, gallery, downloads and reviews.

## Production-ready changes in this version

- Public informational pages no longer require login.
- Password-reset templates are included.
- Applications receive a customer-facing number such as `MAT-20261008-000123`.
- Application status history, customer notifications and admin audit logs are stored.
- Appointment double-booking is blocked for active slots.
- Customer documents are served through an authenticated download endpoint instead of exposing direct file URLs.
- Document verification has pending/verified/rejected states.
- Manual UPI/cash is the default payment flow and does not add gateway fees.
- Razorpay is optional and only enabled when explicitly configured.
- Email supports free HTTP providers (Brevo/Resend) and a console fallback for development.
- Render no longer provisions its expiring free PostgreSQL database; provide an external PostgreSQL `DATABASE_URL` such as a free Supabase project.
- Cloudinary is optional locally and becomes the media backend when credentials are configured.
- Demo/test people, fake jobs, fake payment numbers and known test credentials were removed.
- Sitemap now covers public pages and service detail URLs.
- Gallery editing is supported in the custom admin dashboard.
- `.env.example` documents configuration.

## Local setup

1. Create a virtual environment.
2. Install `requirements.txt`.
3. Copy `.env.example` to `.env` and set a `SECRET_KEY`.
4. Leave `DATABASE_URL` empty for local SQLite.
5. Run:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

6. Open `/admin/` and configure **Business Information**, **Payment Settings**, services, charges and required documents.

No fake business/customer data is seeded automatically.

## Free-first production setup

Recommended architecture:

- Render Free web service
- External free PostgreSQL provider (for example Supabase Free)
- Cloudinary Free for media
- Brevo Free or Resend Free for transactional email
- Manual UPI/cash verification as the default payment path

Free services have quotas, inactivity limits or other conditions. They should not be treated as an unlimited production SLA.

## Email

Set `EMAIL_PROVIDER=brevo` and `BREVO_API_KEY`, or `EMAIL_PROVIDER=resend` and `RESEND_API_KEY`. Keep `EMAIL_PROVIDER=console` for local development. Password reset uses the same provider abstraction.

## Payments

`PAYMENT_GATEWAY=manual` is the free-first default. Customers submit UPI transaction details/UTR or choose cash; staff verifies the payment and then marks it paid. Receipts are generated after verification.

Razorpay remains optional and payment processing fees are set by the provider. If enabled, configure the key ID, key secret and webhook secret. The webhook accepts only requests with a valid HMAC signature, verifies captured status/currency/amount against the stored order total, and is idempotent for duplicate captured events. Configure the same webhook secret in the provider dashboard before enabling event delivery.

## Sensitive documents

Customer identity documents are application-private. Use the protected document download route and keep production media storage private where the chosen provider supports it. Do not expose raw document URLs in customer-facing templates.

## Deployment

The included `render.yaml` expects `DATABASE_URL` to be supplied manually. Do not use Render's expiring free Postgres for permanent customer records. Configure Cloudinary and an email provider in the Render environment.

## Operational checklist

Before opening the site to customers:

- Configure real business details and remove placeholders.
- Configure the actual UPI QR/UPI ID and payment instructions.
- Verify every advertised CSC/government service is actually authorized and offered by the center.
- Verify government scheme/job links and dates before publishing.
- Create a real superadmin account and disable/delete unused accounts.
- Configure external PostgreSQL and backups.
- Configure Cloudinary/private document storage.
- Configure a free transactional email provider.
- Set `DEBUG=False`.
- Set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to the real domain.
- Run migrations and `collectstatic`.
- Test registration, password reset, application submission, document upload/download, appointment booking, payment submission/verification, receipt generation and admin permissions on mobile and desktop.

## Authentication and application security

The app uses Django's session authentication and password hashing, with CSRF-protected forms, HTTP-only/Lax session cookies, role checks for administrative pages, and audit events for login, logout, registration, social sign-in and profile changes. Password login, Django admin login, registration, password reset, Google OAuth and public application tracking are database-rate-limited; the counter keys are HMAC fingerprints rather than raw IP addresses or account identifiers. The database table is shared by app workers and does not require Redis.

### Google sign-in (free)

1. In the Google Cloud Console, create/select a project, configure the OAuth consent screen, and create an OAuth **Web application** client. Configure the correct authorized origin and callback URI. Google does not charge for the OAuth protocol itself, but its account/setup policies apply.
2. Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` in your local `.env` or deployment environment. The callback must exactly match the redirect URI registered with Google (for local development, use `http://localhost:8000/auth/google/callback/`).
3. Restart the app and use **Continue with Google**. Existing password accounts are deliberately not auto-linked by matching email; sign in with the password account first and use **Profile → Connect Google**.

OAuth uses one-time session state and PKCE, exchanges the authorization code server-side, retrieves identity through Google's HTTPS userinfo endpoint, and requires a verified email. If the client ID/secret are absent, password authentication continues to work.

### Encryption at rest and file migration

New application document uploads are encrypted with Fernet authenticated encryption before being written to the configured local or Cloudinary media backend (new files are stored under `encrypted-documents/`). The key is read from `FILE_ENCRYPTION_KEY`; if unset, a domain-separated key is derived from `SECRET_KEY`. For production, configure a dedicated Fernet key and keep it stable in secret management/backups; losing or changing it makes encrypted documents unreadable. Generate one with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

After deploying the new code, back up your media and database, set the key, then migrate legacy unencrypted uploads:

```bash
python manage.py migrate
python manage.py encrypt_existing_documents --dry-run
python manage.py encrypt_existing_documents
```

The command keeps legacy files in place if encryption fails. Existing legacy documents remain readable until migrated. Database encryption-at-rest is provided by the chosen database host/disk, not by Django itself; choose a provider/plan with at-rest encryption and use PostgreSQL TLS (`DB_SSL=True`) in production. The application cannot make a provider encrypt its disks by itself.

### Production checklist

- Keep `DEBUG=False`, use a long random `SECRET_KEY`, set exact `ALLOWED_HOSTS`, and set HTTPS `CSRF_TRUSTED_ORIGINS`.
- Use HTTPS end-to-end, set `BASE_URL` and `GOOGLE_OAUTH_REDIRECT_URI` to HTTPS, and configure a trusted TLS proxy. Do not set `RATE_LIMIT_TRUST_X_FORWARDED_FOR=True` unless your ingress proxy strips/sets that header and is trusted.
- Use PostgreSQL rather than SQLite for multi-worker deployment, run `python manage.py migrate`, `python manage.py check --deploy`, and `python manage.py test` during release.
- Configure regular encrypted backups and retain `FILE_ENCRYPTION_KEY` separately from the database/media backup. Restrict staff accounts and audit-log access; use separate named accounts instead of sharing administrator credentials.
- `RateLimitBucket` uses the database and needs cleanup; the app opportunistically removes expired counters. At high traffic, use edge/WAF limits in addition to application limits.
- Logs avoid passwords/tokens. Review operational logs and set log retention/access controls. Application-level encryption of documents does not replace disk/database encryption or least-privilege storage controls.
