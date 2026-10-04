from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from .models import ClothRoll, Loft, RackLock

User = get_user_model()


class RackLockApiTests(TestCase):
    def setUp(self):
        self.loft = Loft.objects.create(name="北岸帆布间")
        self.other_loft = Loft.objects.create(name="南仓帆布间")
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.ROLE_ADMIN
        )
        self.worker = User.objects.create_user(
            username="worker", password="x", role=User.ROLE_WORKER
        )
        self.client = APIClient()

    def as_worker(self):
        self.client.force_authenticate(self.worker)

    def as_admin(self):
        self.client.force_authenticate(self.admin)

    def place_lock(self, loft=None, seal="SN-001"):
        return self.client.post(
            "/api/locks/", {"loftId": (loft or self.loft).id, "sealNumber": seal}, format="json"
        )

    def test_worker_can_place_lock(self):
        self.as_worker()
        resp = self.place_lock()
        self.assertEqual(resp.status_code, 201, resp.data)
        lock = RackLock.objects.get()
        self.assertEqual(lock.locked_by, self.worker)
        self.assertIsNone(lock.voided_at)
        self.assertEqual(resp.data["lockedBy"], "worker")
        self.assertIn("lockedAt", resp.data)

    def test_blank_seal_rejected(self):
        self.as_worker()
        for bad in ("", "   "):
            resp = self.place_lock(seal=bad)
            self.assertEqual(resp.status_code, 400)
        self.assertEqual(RackLock.objects.count(), 0)

    def test_duplicate_active_seal_same_loft_rejected(self):
        self.as_worker()
        self.assertEqual(self.place_lock().status_code, 201)
        resp = self.place_lock()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("不能重复落锁", resp.data["sealNumber"][0])
        self.assertEqual(RackLock.objects.count(), 1)

    def test_same_seal_other_loft_allowed(self):
        self.as_worker()
        self.assertEqual(self.place_lock().status_code, 201)
        resp = self.place_lock(loft=self.other_loft)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_db_constraint_blocks_double_active_seal(self):
        # 两名仓管同间同号抢锁时，数据库部分唯一约束只放行一把。
        RackLock.objects.create(
            loft=self.loft, seal_number="SN-001", locked_by=self.worker
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RackLock.objects.create(
                    loft=self.loft, seal_number="SN-001", locked_by=self.admin
                )
        self.assertEqual(
            RackLock.objects.filter(loft=self.loft, voided_at__isnull=True).count(), 1
        )

    def test_void_requires_admin(self):
        self.as_worker()
        lock_id = self.place_lock().data["id"]
        resp = self.client.post(f"/api/locks/{lock_id}/void/")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("仅管理员", resp.data["detail"])
        self.assertIsNone(RackLock.objects.get().voided_at)

        self.as_admin()
        resp = self.client.post(f"/api/locks/{lock_id}/void/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(RackLock.objects.get().voided_at)

    def test_revoid_rejected(self):
        self.as_admin()
        lock_id = self.place_lock().data["id"]
        self.assertEqual(self.client.post(f"/api/locks/{lock_id}/void/").status_code, 200)
        resp = self.client.post(f"/api/locks/{lock_id}/void/")
        self.assertEqual(resp.status_code, 400)

    def test_seal_reissuable_after_void(self):
        self.as_worker()
        lock_id = self.place_lock().data["id"]
        self.as_admin()
        self.client.post(f"/api/locks/{lock_id}/void/")
        self.as_worker()
        resp = self.place_lock()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(RackLock.objects.count(), 2)
        self.assertEqual(RackLock.objects.filter(voided_at__isnull=True).count(), 1)

    def test_lock_list_filters(self):
        self.as_worker()
        self.place_lock(seal="SN-001")
        self.place_lock(seal="SN-002")
        voided_id = RackLock.objects.get(seal_number="SN-002").id
        self.as_admin()
        self.client.post(f"/api/locks/{voided_id}/void/")

        active = self.client.get("/api/locks/", {"state": "active"}).data["results"]
        self.assertEqual([row["sealNumber"] for row in active], ["SN-001"])
        voided = self.client.get("/api/locks/", {"state": "voided"}).data["results"]
        self.assertEqual([row["sealNumber"] for row in voided], ["SN-002"])
        by_loft = self.client.get("/api/locks/", {"loftId": self.other_loft.id}).data["results"]
        self.assertEqual(by_loft, [])

    def test_unauthenticated_rejected(self):
        resp = self.client.get("/api/locks/")
        self.assertEqual(resp.status_code, 401)


class RollLockBindingTests(TestCase):
    def setUp(self):
        self.loft = Loft.objects.create(name="北岸帆布间")
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.ROLE_ADMIN
        )
        self.worker = User.objects.create_user(
            username="worker", password="x", role=User.ROLE_WORKER
        )
        self.client = APIClient()
        self.client.force_authenticate(self.worker)

    def create_roll(self, code="R-10"):
        return self.client.post(
            "/api/rolls/",
            {"loftId": self.loft.id, "rollCode": code, "fabricWeightGsm": 400},
            format="json",
        )

    def test_roll_create_blocked_without_lock(self):
        resp = self.create_roll()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("铅封锁", resp.data["detail"])
        self.assertEqual(ClothRoll.objects.count(), 0)

    def test_roll_create_blocked_when_only_voided_lock(self):
        lock = RackLock.objects.create(
            loft=self.loft, seal_number="SN-001", locked_by=self.worker
        )
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/locks/{lock.id}/void/")
        resp = self.create_roll()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ClothRoll.objects.count(), 0)

    def test_roll_create_binds_lock_and_consumes_it(self):
        lock = RackLock.objects.create(
            loft=self.loft, seal_number="SN-001", locked_by=self.worker
        )
        resp = self.create_roll()
        self.assertEqual(resp.status_code, 201, resp.data)
        lock.refresh_from_db()
        self.assertEqual(lock.roll_id, resp.data["id"])
        self.assertEqual(resp.data["sealNumber"], "SN-001")
        # 锁已被绑走，再建卷须重新落锁
        resp2 = self.create_roll(code="R-11")
        self.assertEqual(resp2.status_code, 400)
        self.assertEqual(ClothRoll.objects.count(), 1)

    def test_roll_patch_weight_and_notes_needs_no_lock(self):
        roll = ClothRoll.objects.create(
            loft=self.loft, roll_code="R-01", fabric_weight_gsm=380
        )
        resp = self.client.patch(
            f"/api/rolls/{roll.id}/",
            {"fabricWeightGsm": 420, "notes": "复称后修正"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        roll.refresh_from_db()
        self.assertEqual(roll.fabric_weight_gsm, 420)
        self.assertEqual(roll.notes, "复称后修正")

    def test_cured_rule_unchanged(self):
        roll = ClothRoll.objects.create(loft=self.loft, roll_code="R-01")
        resp = self.client.patch(
            f"/api/rolls/{roll.id}/", {"status": "cured"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("已固化", resp.data["status"][0])
