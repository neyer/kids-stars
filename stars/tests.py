from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Kid, StarTransaction


class QuickTapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("parent", password="pw")
        self.client.force_login(self.user)
        self.kid = Kid.objects.get(name="Allie")
        self.other = Kid.objects.get(name="Paul")

    def tap(self, kid, direction="add", reason=""):
        return self.client.post(
            reverse("stars:tap", args=[kid.id]), {"direction": direction, "reason": reason}
        )

    def test_page_shows_all_kids(self):
        resp = self.client.get(reverse("stars:quick_tap"))
        for name in ["Allie", "Paul", "Charlotte"]:
            self.assertContains(resp, name)

    def test_ten_taps_make_one_plus_ten_record(self):
        for _ in range(10):
            resp = self.tap(self.kid)
        self.assertEqual(resp.json()["balance"], 10)
        self.assertEqual(resp.json()["chunk"], 10)
        txns = list(self.kid.transactions.all())
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0].delta, 10)
        self.assertEqual(txns[0].reason, "")

    def test_minus_taps_merge_and_cancel(self):
        for _ in range(3):
            self.tap(self.kid)
        self.tap(self.kid, "remove")
        self.assertEqual([t.delta for t in self.kid.transactions.all()], [2])
        self.tap(self.kid, "remove")
        self.tap(self.kid, "remove")
        self.assertEqual(self.kid.transactions.count(), 0)

    def test_kids_chunk_independently(self):
        self.tap(self.kid)
        self.tap(self.other)
        self.tap(self.kid)
        self.assertEqual([t.delta for t in self.kid.transactions.all()], [2])
        self.assertEqual([t.delta for t in self.other.transactions.all()], [1])

    def test_does_not_merge_into_entry_with_reason(self):
        StarTransaction.objects.create(kid=self.kid, delta=1, reason="Dinner on time")
        self.tap(self.kid)
        self.assertEqual(self.kid.transactions.count(), 2)

    def test_same_reason_merges(self):
        for _ in range(3):
            self.tap(self.kid, reason="  cleaned room ")
        txns = list(self.kid.transactions.all())
        self.assertEqual([(t.delta, t.reason) for t in txns], [(3, "cleaned room")])

    def test_changing_reason_starts_new_entry(self):
        self.tap(self.kid, reason="cleaned room")
        self.tap(self.kid, reason="cleaned room")
        self.tap(self.kid, reason="fed the dog")
        self.tap(self.kid)
        self.assertEqual(
            [(t.delta, t.reason) for t in self.kid.transactions.all()],
            [(1, ""), (1, "fed the dog"), (2, "cleaned room")],
        )

    def test_does_not_merge_after_window(self):
        self.tap(self.kid)
        old = timezone.now() - timedelta(minutes=5)
        StarTransaction.objects.update(created_at=old, updated_at=old)
        self.tap(self.kid)
        self.assertEqual([t.delta for t in self.kid.transactions.all()], [1, 1])

    def test_requires_login(self):
        self.client.logout()
        self.tap(self.kid)
        self.assertEqual(self.kid.transactions.count(), 0)
