from django.conf import settings
from django.db import models
from django.utils import timezone


class Loft(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class ClothRoll(models.Model):
    STATUS_RAW = "raw"
    STATUS_DIPPING = "dipping"
    STATUS_CURED = "cured"
    STATUS_CHOICES = [
        (STATUS_RAW, "原布"),
        (STATUS_DIPPING, "浸渍中"),
        (STATUS_CURED, "已固化"),
    ]

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="rolls")
    roll_code = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RAW)
    fabric_weight_gsm = models.PositiveIntegerField(default=380)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loft_id", "roll_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["loft", "roll_code"],
                name="uniq_roll_code_per_loft",
            )
        ]

    def __str__(self):
        return f"{self.loft.name}/{self.roll_code}"


class DipRun(models.Model):
    roll = models.ForeignKey(ClothRoll, on_delete=models.CASCADE, related_name="dip_runs")
    started_at = models.DateTimeField()
    resin_pct = models.DecimalField(max_digits=5, decimal_places=2)
    cure_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Dip@{self.roll_id} {self.started_at}"


class RackLock(models.Model):
    """铅封锁：新布卷入晾晒架前，须先在帆布间落一条未作废铅封号。

    roll 为空表示该锁尚未绑卷（可用）；建卷成功时在同一事务里写入。
    """

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="rack_locks")
    seal_number = models.CharField(max_length=60)
    locked_at = models.DateTimeField(default=timezone.now)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rack_locks",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    roll = models.OneToOneField(
        ClothRoll,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rack_lock",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-locked_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(seal_number=""),
                name="racklock_seal_number_nonempty",
            ),
            models.UniqueConstraint(
                fields=["loft", "seal_number"],
                condition=models.Q(voided_at__isnull=True),
                name="uniq_active_seal_per_loft",
            ),
        ]

    def __str__(self):
        state = "已作废" if self.voided_at else "未作废"
        return f"{self.loft.name}/{self.seal_number} ({state})"
