from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, Loft, RackLock
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    RackLockSerializer,
)

User = get_user_model()

NO_AVAILABLE_LOCK_MSG = "该帆布间暂无未作废的可用铅封锁，请先在「铅封锁」页落锁后再新建布卷"
DUPLICATE_SEAL_MSG = "该帆布间已存在未作废的相同铅封号，不能重复落锁"


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft", "rack_lock").all()
        loft_id = self.request.query_params.get("loftId")
        status = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status:
            qs = qs.filter(status=status)
        return qs

    def create(self, request, *args, **kwargs):
        # 建卷与绑锁必须在同一事务里完成：任一步失败整体回滚。
        try:
            with transaction.atomic():
                return super().create(request, *args, **kwargs)
        except IntegrityError:
            raise ValidationError({"detail": "铅封锁绑定冲突，请刷新架面后重试"})

    def perform_create(self, serializer):
        loft = serializer.validated_data["loft"]
        # 取该间最早落下、未作废且未绑卷的锁；行锁防止并发建卷抢同一把锁。
        lock = (
            RackLock.objects.select_for_update()
            .filter(loft=loft, voided_at__isnull=True, roll__isnull=True)
            .order_by("locked_at", "id")
            .first()
        )
        if lock is None:
            raise ValidationError({"detail": NO_AVAILABLE_LOCK_MSG})
        roll = serializer.save()
        lock.roll = roll
        lock.save(update_fields=["roll"])


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs


class RackLockViewSet(viewsets.ModelViewSet):
    """铅封锁：操作工可落锁；作废仅管理员；锁只落不删。"""

    serializer_class = RackLockSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = RackLock.objects.select_related("loft", "locked_by", "roll").all()
        params = self.request.query_params
        loft_id = params.get("loftId")
        state = params.get("state")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if state == "active":
            qs = qs.filter(voided_at__isnull=True)
        elif state == "voided":
            qs = qs.filter(voided_at__isnull=False)
        if params.get("available") in ("1", "true"):
            # 可绑新卷的锁：未作废且未绑卷；按落锁先后排，队首即建卷时将绑定的那把。
            qs = qs.filter(voided_at__isnull=True, roll__isnull=True).order_by(
                "locked_at", "id"
            )
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save(locked_by=request.user)
        except IntegrityError:
            # 两人同间同号同时落锁：数据库部分唯一约束只放行一把，
            # 被挡者在此拿到干净的中文 400，事务已回滚，后续请求不受影响。
            raise ValidationError({"sealNumber": DUPLICATE_SEAL_MSG})
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        if request.user.role != User.ROLE_ADMIN:
            raise PermissionDenied("仅管理员可作废铅封锁")
        with transaction.atomic():
            lock = get_object_or_404(
                RackLock.objects.select_for_update(), pk=pk
            )
            if lock.voided_at is not None:
                raise ValidationError({"detail": "该铅封锁已作废，不能重复作废"})
            lock.voided_at = timezone.now()
            lock.save(update_fields=["voided_at"])
        return Response(self.get_serializer(lock).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
    }
    return Response(data)
