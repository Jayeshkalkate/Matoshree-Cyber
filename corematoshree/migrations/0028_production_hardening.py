# Generated manually for production hardening.
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_application_numbers(apps, schema_editor):
    Application = apps.get_model('corematoshree', 'Application')
    for app in Application.objects.filter(application_number__isnull=True).order_by('id'):
        created = app.created_at or django.utils.timezone.now()
        app.application_number = f"MAT-{created.strftime('%Y%m%d')}-{app.pk:06d}"
        app.save(update_fields=['application_number'])


def reverse_application_numbers(apps, schema_editor):
    Application = apps.get_model('corematoshree', 'Application')
    Application.objects.update(application_number=None)


class Migration(migrations.Migration):
    dependencies = [
        ('corematoshree', '0027_alter_governmentscheme_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='application', name='application_number',
            field=models.CharField(blank=True, db_index=True, max_length=40, null=True, unique=True, verbose_name='Application Number'),
        ),
        migrations.AddField(
            model_name='application', name='admin_note',
            field=models.TextField(blank=True, verbose_name='Admin Note'),
        ),
        migrations.AddField(
            model_name='application', name='rejection_reason',
            field=models.TextField(blank=True, verbose_name='Rejection Reason'),
        ),
        migrations.RunPython(backfill_application_numbers, reverse_application_numbers),
        migrations.AddField(
            model_name='documentupload', name='verification_status',
            field=models.CharField(choices=[('pending','Pending'),('verified','Verified'),('rejected','Rejected')], db_index=True, default='pending', max_length=20, verbose_name='Verification Status'),
        ),
        migrations.AddField(
            model_name='documentupload', name='verification_note',
            field=models.TextField(blank=True, verbose_name='Verification Note'),
        ),
        migrations.AddField(
            model_name='documentupload', name='verified_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Verified At'),
        ),
        migrations.AddField(
            model_name='documentupload', name='verified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_documents', to='corematoshree.user'),
        ),
        migrations.CreateModel(
            name='ApplicationStatusHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_status', models.CharField(blank=True, max_length=20)),
                ('new_status', models.CharField(max_length=20)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_history', to='corematoshree.application')),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='application_status_changes', to='corematoshree.user')),
            ],
            options={'ordering':['created_at']},
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='corematoshree.application')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='corematoshree.user')),
            ],
            options={'ordering':['-created_at']},
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(db_index=True, max_length=100)),
                ('model_name', models.CharField(blank=True, max_length=100)),
                ('object_id', models.CharField(blank=True, max_length=100)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='corematoshree.user')),
            ],
            options={'ordering':['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='appointment',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ['Pending','Confirmed'])), fields=('appointment_date','appointment_time'), name='unique_active_appointment_slot'),
        ),
        migrations.AlterField(
            model_name='paymentlog', name='event_type',
            field=models.CharField(choices=[('created','Order Created'),('captured','Payment Captured'),('failed','Payment Failed'),('refunded','Payment Refunded'),('webhook_received','Webhook Received'),('manual_submitted','Manual Payment Submitted'),('manual_confirmed','Manually Confirmed')], db_index=True, max_length=50, verbose_name='Event Type'),
        ),
    ]
