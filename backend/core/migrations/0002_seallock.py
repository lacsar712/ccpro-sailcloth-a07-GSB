import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SealLock",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("seal_number", models.CharField(max_length=60)),
                ("locked_at", models.DateTimeField(auto_now_add=True)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                (
                    "loft",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seal_locks",
                        to="core.loft",
                    ),
                ),
                (
                    "locked_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="seal_locks_locked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "voided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="seal_locks_voided",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "roll",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seal_lock",
                        to="core.clothroll",
                    ),
                ),
            ],
            options={
                "ordering": ["-locked_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="seallock",
            constraint=models.UniqueConstraint(
                condition=models.Q(("voided_at__isnull", True)),
                fields=("loft", "seal_number"),
                name="uniq_active_seal_number_per_loft",
            ),
        ),
    ]
