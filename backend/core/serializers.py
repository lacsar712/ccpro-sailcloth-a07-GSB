from django.db import transaction
from rest_framework import serializers

from .models import ClothRoll, DipRun, Loft, SealLock
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
    sealNumber = serializers.SerializerMethodField()
    sealLockId = serializers.PrimaryKeyRelatedField(
        queryset=SealLock.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
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
            "sealLockId",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "sealNumber", "created_at", "updated_at")

    def get_sealNumber(self, obj):
        seal = getattr(obj, "seal_lock", None)
        if seal is None:
            return None
        return seal.seal_number

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

    def create(self, validated_data):
        requested_lock = validated_data.pop("sealLockId", None)
        # 建卷与绑锁必须同一事务：无未作废锁则整体回滚，绝不允许无锁卷或绑锁分叉。
        with transaction.atomic():
            roll = super().create(validated_data)
            locks = (
                SealLock.objects.select_for_update()
                .filter(loft=roll.loft, voided_at__isnull=True, roll__isnull=True)
            )
            if requested_lock is not None:
                # 前端点新建时读到的那把锁；若已被并发占用/作废则视为无锁
                lock = locks.filter(pk=requested_lock.pk).first()
            else:
                lock = locks.order_by("locked_at", "id").first()
            if lock is None:
                raise serializers.ValidationError(
                    {"sealLock": "该帆布间没有未作废且未使用的铅封锁，不能新建布卷；请先落锁。"}
                )
            lock.roll = roll
            lock.save(update_fields=["roll"])
        return roll

    def update(self, instance, validated_data):
        # 改已有卷（克重/备注/状态）不涉及锁，忽略客户端可能传入的 sealLockId
        validated_data.pop("sealLockId", None)
        return super().update(instance, validated_data)


class SealLockSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    sealNumber = serializers.CharField(source="seal_number")
    loftName = serializers.CharField(source="loft.name", read_only=True)
    lockedAt = serializers.DateTimeField(source="locked_at", read_only=True)
    lockedBy = serializers.CharField(source="locked_by.username", read_only=True)
    voidedAt = serializers.DateTimeField(source="voided_at", read_only=True)
    voidedBy = serializers.CharField(source="voided_by.username", read_only=True)
    rollId = serializers.IntegerField(source="roll_id", read_only=True)
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    active = serializers.BooleanField(source="is_active", read_only=True)
    bound = serializers.BooleanField(source="is_bound", read_only=True)

    class Meta:
        model = SealLock
        fields = (
            "id",
            "loftId",
            "loftName",
            "sealNumber",
            "lockedAt",
            "lockedBy",
            "voidedAt",
            "voidedBy",
            "rollId",
            "rollCode",
            "active",
            "bound",
        )
        # locked_by 取自请求用户；voided_* 只许由作废 action 写入
        read_only_fields = (
            "id",
            "loftName",
            "lockedAt",
            "lockedBy",
            "voidedAt",
            "voidedBy",
            "rollId",
            "rollCode",
            "active",
            "bound",
        )

    def validate_seal_number(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("铅封号不得为空")
        return value

    def validate(self, attrs):
        loft = attrs.get("loft")
        seal_number = attrs.get("seal_number")
        if loft and seal_number:
            exists = SealLock.objects.filter(
                loft=loft, seal_number=seal_number, voided_at__isnull=True
            ).exists()
            if exists:
                raise serializers.ValidationError(
                    {"sealNumber": "该帆布间已有同号未作废铅封锁，不能重复落锁"}
                )
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
