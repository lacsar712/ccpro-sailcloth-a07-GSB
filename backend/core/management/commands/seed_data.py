from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import ClothRoll, DipRun, Loft, SealLock

User = get_user_model()


class Command(BaseCommand):
    help = "初始化演示账号与帆布间种子数据（一间零锁）"

    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@sailcloth.local",
                "role": User.ROLE_ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password("123456")
        admin.role = User.ROLE_ADMIN
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        self.stdout.write(self.style.SUCCESS(f"admin {'created' if created else 'updated'}"))

        worker, created = User.objects.get_or_create(
            username="worker",
            defaults={
                "email": "worker@sailcloth.local",
                "role": User.ROLE_WORKER,
            },
        )
        worker.set_password("123456")
        worker.role = User.ROLE_WORKER
        worker.save()
        self.stdout.write(self.style.SUCCESS(f"worker {'created' if created else 'updated'}"))

        if Loft.objects.exists():
            self.stdout.write("帆布间已存在，跳过业务种子写入。")
            return

        Loft.objects.create(
            name="北岸帆布间",
            location="港区二号库",
            notes="浸渍防水台示范 loft；新卷入架前请先落铅封锁。",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"种子完成：帆布间 {Loft.objects.count()}，布卷 {ClothRoll.objects.count()}，"
                f"浸渍 {DipRun.objects.count()}，铅封锁 {SealLock.objects.count()}"
            )
        )
