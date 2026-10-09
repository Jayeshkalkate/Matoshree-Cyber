# Security hardening: Google identities, DB-backed rate limits, encrypted documents.
import django.db.models.deletion
import corematoshree.storage
from django.conf import settings
from django.db import migrations, models


def promote_existing_superusers(apps, schema_editor):
    """Keep Django superusers aligned with the application's RBAC role labels."""
    User = apps.get_model("corematoshree", "User")
    User.objects.filter(is_superuser=True).exclude(role="superadmin").update(role="superadmin")


def noop_reverse(apps, schema_editor):
    # A demotion would risk stripping privileges from real superuser accounts.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("corematoshree", "0030_remove_application_admin_note_and_more"),
    ]

    operations = [
        migrations.RunPython(promote_existing_superusers, noop_reverse),
        migrations.AlterField(
            model_name="documentupload",
            name="file",
            field=models.FileField(
                storage=corematoshree.storage.EncryptedDocumentStorage(),
                upload_to="applications/%Y/%m/%d/",
                verbose_name="File",
            ),
        ),
        migrations.CreateModel(
            name="SocialIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("google", "Google")], default="google", max_length=30)),
                ("subject", models.CharField(help_text="Stable provider subject; never an access token.", max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="social_identities", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="socialidentity",
            constraint=models.UniqueConstraint(fields=("provider", "subject"), name="unique_social_provider_subject"),
        ),
        migrations.AddIndex(
            model_name="socialidentity",
            index=models.Index(fields=["user", "provider"], name="social_id_user_provider_idx"),
        ),
        migrations.CreateModel(
            name="RateLimitBucket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("window_started", models.DateTimeField(db_index=True)),
                ("count", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="ratelimitbucket",
            index=models.Index(fields=["window_started", "count"], name="ratelimit_window_count_idx"),
        ),
    ]
