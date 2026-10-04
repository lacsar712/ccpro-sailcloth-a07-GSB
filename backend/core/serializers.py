from rest_framework import serializers

from .models import ClothRoll, DipRun, Loft, RackLock
from .rules import can_mark_roll_cured


class LoftSerializer(serializers.ModelSerializer):
    rollCount = serializers.SerializerMethodField()

    class Meta:
        model = Loft
        fields = ("id", "name", "location", "notes", "rollCount", "created_at")
        read_only_fields = ("id", "rollCount", "created_at")

    def get_rollCount(self, obj):
        if hasattr(obj, "roll_count"):
            return obj.roll_count
        return obj.rolls.count()


class ClothRollSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    rollCode = serializers.CharField(source="roll_code")
    fabricWeightGsm = serializers.IntegerField(source="fabric_weight_gsm", required=False)
    loftName = serializers.CharField(source="loft.name", read_only=True)
    sealNumber = serializers.CharField(
        source="rack_lock.seal_number", read_only=True, default=None
    )

    class Meta:
        model = ClothRoll
        fields = (
            "id",
            "loftId",
            "loftName",
            "rollCode",
            "status",
            "fabricWeightGsm",
            "notes",
            "sealNumber",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "sealNumber", "created_at", "updated_at")

    def validate(self, attrs):
        loft = attrs.get("loft") or getattr(self.instance, "loft", None)
        roll_code = attrs.get("roll_code") or getattr(self.instance, "roll_code", None)
        if loft and roll_code:
            qs = ClothRoll.objects.filter(loft=loft, roll_code=roll_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"rollCode": "同一帆布间卷号必须唯一"})

        new_status = attrs.get("status")
        if new_status == ClothRoll.STATUS_CURED:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为已固化"}
                )
            # 合并未提交字段到临时视角：用当前实例校验
            ok, msg = can_mark_roll_cured(roll)
            if not ok:
                raise serializers.ValidationError({"status": msg})
        return attrs


class DipRunSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    startedAt = serializers.DateTimeField(source="started_at")
    resinPct = serializers.DecimalField(source="resin_pct", max_digits=5, decimal_places=2)
    cureHours = serializers.DecimalField(
        source="cure_hours",
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)

    class Meta:
        model = DipRun
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "startedAt",
            "resinPct",
            "cureHours",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "rollCode", "loftName", "created_at")


class RackLockSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    loftName = serializers.CharField(source="loft.name", read_only=True)
    sealNumber = serializers.CharField(source="seal_number", max_length=60)
    lockedAt = serializers.DateTimeField(source="locked_at", read_only=True)
    lockedBy = serializers.CharField(source="locked_by.username", read_only=True)
    voidedAt = serializers.DateTimeField(source="voided_at", read_only=True)
    rollId = serializers.PrimaryKeyRelatedField(source="roll", read_only=True)
    rollCode = serializers.CharField(
        source="roll.roll_code", read_only=True, default=None
    )

    class Meta:
        model = RackLock
        fields = (
            "id",
            "loftId",
            "loftName",
            "sealNumber",
            "lockedAt",
            "lockedBy",
            "voidedAt",
            "rollId",
            "rollCode",
        )
        read_only_fields = (
            "id",
            "loftName",
            "lockedAt",
            "lockedBy",
            "voidedAt",
            "rollId",
            "rollCode",
        )

    def validate_sealNumber(self, value):
        seal = value.strip()
        if not seal:
            raise serializers.ValidationError("铅封号不能为空")
        return seal

    def validate(self, attrs):
        loft = attrs.get("loft")
        seal = attrs.get("seal_number")
        if loft and seal:
            dup = RackLock.objects.filter(
                loft=loft, seal_number=seal, voided_at__isnull=True
            ).exists()
            if dup:
                raise serializers.ValidationError(
                    {"sealNumber": f"帆布间「{loft.name}」已存在未作废的铅封号 {seal}，不能重复落锁"}
                )
        return attrs
