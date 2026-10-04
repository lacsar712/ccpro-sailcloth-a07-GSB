from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from .models import ClothRoll, DipRun, Loft, SealLock
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    SealLockSerializer,
)


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft", "seal_lock").all()
        loft_id = self.request.query_params.get("loftId")
        status_param = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class SealLockViewSet(viewsets.ModelViewSet):
    serializer_class = SealLockSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = SealLock.objects.select_related("loft", "locked_by", "voided_by", "roll").all()
        params = self.request.query_params
        loft_id = params.get("loftId")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)

        state = params.get("state")
        if state == "active":
            qs = qs.filter(voided_at__isnull=True)
        elif state == "voided":
            qs = qs.filter(voided_at__isnull=False)

        bound = params.get("bound")
        if bound == "false":
            qs = qs.filter(roll__isnull=True)
        elif bound == "true":
            qs = qs.filter(roll__isnull=False)
        return qs

    def perform_create(self, serializer):
        # 串行化校验与插入：两名仓管同间同号并发落锁时，数据库部分唯一索引
        # 只放一把入库；IntegrityError 在本保存点转成中文 400，架面/页面不受影响。
        try:
            with transaction.atomic():
                serializer.save(locked_by=self.request.user)
        except IntegrityError:
            raise ValidationError(
                {"sealNumber": "该帆布间已有同号未作废铅封锁，不能重复落锁"}
            )

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        if request.user.role != "admin":
            return Response(
                {"detail": "只有管理员可以作废铅封锁"},
                status=status.HTTP_403_FORBIDDEN,
            )
        lock = self.get_object()
        if lock.voided_at is not None:
            return Response(
                {"detail": "该铅封锁已经作废，无需重复作废"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        lock.voided_at = timezone.now()
        lock.voided_by = request.user
        lock.save(update_fields=["voided_at", "voided_by"])
        return Response(self.get_serializer(lock).data)


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs


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
