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

Razorpay remains optional. If enabled, configure all Razorpay secrets and implement the provider webhook endpoint with the provider's current signing requirements before relying on it in production.

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
