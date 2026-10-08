from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('corematoshree', '0028_production_hardening')]

    operations = [
        migrations.AddField(
            model_name='jobnotification', name='source',
            field=models.URLField(blank=True, verbose_name='Source URL'),
        ),
        migrations.AddField(
            model_name='jobnotification', name='verified',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Verified'),
        ),
        migrations.AddField(
            model_name='governmentscheme', name='verified',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Verified'),
        ),
        migrations.AddField(
            model_name='governmentscheme', name='verified_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Verified At'),
        ),
    ]
