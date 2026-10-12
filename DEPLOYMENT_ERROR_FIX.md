# Render homepage 500: deployment diagnosis and fix

## What the supplied logs prove

The exception is a Django `FieldError` from a query in `core/views.py`:

```python
Scheme.objects.filter(published__lte=timezone.now()).order_by('-published')[:3]
```

The model fields listed in that same traceback do **not** include `published`. Django therefore cannot build the query. The process binding to port 10000 is not the cause.

## Important source/repository mismatch

The supplied Matoshree project ZIP does not contain `core/views.py` or a `Scheme` model. Its Django application is `corematoshree`, its model is `GovernmentScheme`, and its public homepage is `corematoshree.views.home`. That homepage does not issue the invalid `published` query. This means the Render service that produced the logs is running a different code layout or repository revision from this ZIP.

Do not try to solve this by adding a `published` field to the supplied project's model: it would not fix the code path in the deployed service, and it would add a database migration without evidence that this field belongs in the schema.

## Fix if you are keeping the currently deployed legacy repository

In that repository's `core/views.py`, replace the invalid query with a query using a field that actually exists in that repository's `Scheme` model. The traceback lists `updated`, so the safest recent-items query is:

```python
'schemes': Scheme.objects.order_by('-updated')[:3],
```

This removes the invalid publication-date filter. If the homepage specifically needs date-based eligibility, implement that business rule using the existing `start_date` and/or `end_date` fields instead; do not call them `published` unless you add and maintain a real publication field in the model and a corresponding migration.

Then commit and push the change to the exact branch connected to the Render web service, confirm the service is building that commit, and deploy. Check the homepage with both `GET /` and `HEAD /` after deployment.

## If you intend to deploy this Matoshree ZIP instead

1. Push this project's source to the repository/branch intended for the service.
2. Confirm Render is connected to that repository and branch, not the older code that has `core/views.py`.
3. Configure `DATABASE_URL`, `SECRET_KEY`, the actual domain in `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`, and any required media, email, OAuth, and payment secrets in the Render dashboard. Never put production secrets in this ZIP.
4. Ensure the `BASE_URL`, Google OAuth callback URL, and static loader URL target the domain actually used by the service. The checked-in `render.yaml` currently names the service `matoshree-cyber`; the logs provided are from `lok-setu.onrender.com`. Do not deploy the blueprint unchanged if those are intended to be the same live service; reconcile the service/domain configuration first.
5. After deploy, run `python manage.py migrate --check`, `python manage.py check --deploy`, and `python manage.py test` in an environment with the production dependencies installed. Verify homepage, authentication, document access, payments, and receipt generation manually before opening it to the public.

The `/healthz/` endpoint is designed to be a lightweight process health probe and does not exercise the homepage's database queries or template. Keep a separate homepage smoke check as well; this release adds a test for that route.
