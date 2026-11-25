import json
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ApiToken, Kid, QuickAction, StarRequest, StarTransaction


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


class KidLoginTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user("parent", password="pw")
        self.allie = Kid.objects.get(name="Allie")
        self.paul = Kid.objects.get(name="Paul")
        self.allie.user = User.objects.create_user("allie", password="pw")
        self.allie.save()

    def login_kid(self):
        self.client.force_login(self.allie.user)

    def test_kid_home_redirects_to_own_page(self):
        self.login_kid()
        resp = self.client.get(reverse("stars:kid_list"))
        self.assertRedirects(resp, reverse("stars:kid_detail", args=[self.allie.id]))

    def test_kid_cannot_change_stars(self):
        self.login_kid()
        action = QuickAction.objects.filter(delta__gt=0).first()
        urls = [
            (reverse("stars:add_stars", args=[self.allie.id]), {"amount": 5, "direction": "add"}),
            (reverse("stars:quick_action", args=[self.allie.id, action.id]), {}),
            (reverse("stars:tap", args=[self.allie.id]), {"direction": "add"}),
        ]
        for url, data in urls:
            self.assertEqual(self.client.post(url, data).status_code, 403, url)
        self.assertEqual(self.client.get(reverse("stars:quick_tap")).status_code, 403)
        self.assertEqual(self.client.get(reverse("stars:request_list")).status_code, 403)
        self.assertEqual(self.allie.balance, 0)

    def test_kid_requests_custom_and_listed_activity(self):
        self.login_kid()
        url = reverse("stars:request_stars", args=[self.allie.id])
        self.client.post(url, {"amount": 2, "reason": "Cleaned room"})
        action = QuickAction.objects.filter(delta__gt=0).first()
        self.client.post(url, {"action": action.id})
        reqs = list(StarRequest.objects.order_by("id").values_list("delta", "reason", "status"))
        self.assertEqual(
            reqs, [(2, "Cleaned room", "pending"), (action.delta, action.label, "pending")]
        )
        self.assertEqual(self.allie.balance, 0)

    def test_kid_request_validation(self):
        self.login_kid()
        url = reverse("stars:request_stars", args=[self.allie.id])
        self.client.post(url, {"amount": 2, "reason": ""})
        self.client.post(url, {"amount": 0, "reason": "x"})
        self.client.post(url, {"amount": 1000, "reason": "x"})
        negative = QuickAction.objects.filter(delta__lt=0).first()
        self.client.post(url, {"action": negative.id})
        self.assertEqual(StarRequest.objects.count(), 0)

    def test_kid_cannot_request_for_sibling(self):
        self.login_kid()
        resp = self.client.post(
            reverse("stars:request_stars", args=[self.paul.id]), {"amount": 1, "reason": "x"}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(StarRequest.objects.count(), 0)

    def test_parent_cannot_request(self):
        self.client.force_login(self.parent)
        resp = self.client.post(
            reverse("stars:request_stars", args=[self.allie.id]), {"amount": 1, "reason": "x"}
        )
        self.assertEqual(resp.status_code, 403)

    def test_kid_cancels_own_request(self):
        req = StarRequest.objects.create(kid=self.allie, delta=1, reason="x")
        self.login_kid()
        self.client.post(reverse("stars:cancel_request", args=[req.id]))
        self.assertEqual(StarRequest.objects.count(), 0)

    def test_parent_approves_and_denies(self):
        yes = StarRequest.objects.create(kid=self.allie, delta=3, reason="Homework")
        no = StarRequest.objects.create(kid=self.allie, delta=50, reason="Being awesome")
        self.client.force_login(self.parent)
        self.client.post(reverse("stars:approve_request", args=[yes.id]))
        self.client.post(reverse("stars:deny_request", args=[no.id]))
        # Approving twice doesn't add stars twice.
        resp = self.client.post(reverse("stars:approve_request", args=[yes.id]))
        self.assertEqual(resp.status_code, 404)

        yes.refresh_from_db()
        no.refresh_from_db()
        self.assertEqual((yes.status, no.status), ("approved", "denied"))
        self.assertEqual(yes.decided_by, self.parent)
        self.assertEqual(self.allie.balance, 3)
        self.assertEqual(self.allie.transactions.get().reason, "Homework")

    def test_kid_cannot_approve(self):
        req = StarRequest.objects.create(kid=self.allie, delta=3, reason="x")
        self.login_kid()
        self.assertEqual(
            self.client.post(reverse("stars:approve_request", args=[req.id])).status_code, 403
        )
        self.assertEqual(self.allie.balance, 0)

    def test_requests_page_shows_pending(self):
        StarRequest.objects.create(kid=self.allie, delta=3, reason="Fed the dog")
        self.client.force_login(self.parent)
        resp = self.client.get(reverse("stars:request_list"))
        self.assertContains(resp, "Fed the dog")
        self.assertContains(resp, 'class="badge">1<')

    def test_kid_page_for_each_role(self):
        StarRequest.objects.create(kid=self.allie, delta=3, reason="Fed the dog")
        StarTransaction.objects.create(kid=self.allie, delta=1, reason="dishes")
        url = reverse("stars:kid_detail", args=[self.allie.id])

        self.login_kid()
        resp = self.client.get(url)
        self.assertContains(resp, "Ask for stars")
        self.assertContains(resp, "Fed the dog")
        self.assertNotContains(resp, 'title="Delete entry"')
        # On a sibling's page, a kid sees no controls at all.
        resp = self.client.get(reverse("stars:kid_detail", args=[self.paul.id]))
        self.assertNotContains(resp, "Ask for stars")
        self.assertNotContains(resp, 'name="direction"')

        self.client.force_login(self.parent)
        resp = self.client.get(url)
        self.assertContains(resp, "Waiting for approval")
        self.assertContains(resp, "Approve")
        self.assertContains(resp, 'name="direction"')
        self.assertContains(resp, 'title="Delete entry"')
        self.assertNotContains(resp, "Ask for stars")

    def test_pending_stars_shown_with_balance(self):
        StarRequest.objects.create(kid=self.allie, delta=3, reason="a")
        StarRequest.objects.create(kid=self.allie, delta=2, reason="b")
        StarRequest.objects.create(kid=self.allie, delta=9, reason="c", status=StarRequest.DENIED)
        self.assertEqual(self.allie.pending_stars, 5)
        self.assertEqual(self.paul.pending_stars, 0)

        self.client.force_login(self.parent)
        self.assertContains(self.client.get(reverse("stars:kid_list")), "+5 pending", count=1)
        self.assertContains(self.client.get(reverse("stars:quick_tap")), "+5 pending", count=1)
        resp = self.client.get(reverse("stars:kid_detail", args=[self.allie.id]))
        self.assertContains(resp, "+5 waiting for approval")
        resp = self.client.get(reverse("stars:kid_detail", args=[self.paul.id]))
        self.assertNotContains(resp, "waiting for approval")

    def test_create_kid_login_command(self):
        call_command("create_kid_login", "paul", "paulie", password="secret", stdout=StringIO())
        self.paul.refresh_from_db()
        self.assertEqual(self.paul.user.username, "paulie")
        self.assertTrue(self.paul.user.check_password("secret"))
        self.assertFalse(self.paul.user.is_staff)


class ApiTests(TestCase):
    def setUp(self):
        self.token, self.key = ApiToken.create("test app")
        self.allie = Kid.objects.get(name="Allie")

    def api(self, method, url, body=None, key=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {key or self.key}"}
        if body is not None:
            return getattr(self.client, method)(
                url, json.dumps(body), content_type="application/json", **headers
            )
        return getattr(self.client, method)(url, **headers)

    def test_requires_valid_token(self):
        url = reverse("stars:api_kids")
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.api("get", url, key="wrong").status_code, 401)
        self.token.active = False
        self.token.save()
        self.assertEqual(self.api("get", url).status_code, 401)

    def test_key_is_not_stored(self):
        self.assertNotIn(self.key, self.token.key_hash)
        self.assertNotEqual(self.key, self.token.key_hash)

    def test_list_kids(self):
        StarTransaction.objects.create(kid=self.allie, delta=4)
        data = self.api("get", reverse("stars:api_kids")).json()
        self.assertEqual([k["name"] for k in data["kids"]], ["Allie", "Paul", "Charlotte"])
        self.assertEqual(data["kids"][0]["balance"], 4)
        self.token.refresh_from_db()
        self.assertIsNotNone(self.token.last_used_at)

    def test_kid_detail_by_id_or_name(self):
        StarTransaction.objects.create(kid=self.allie, delta=2, reason="dishes")
        for ref in [str(self.allie.id), "allie"]:
            data = self.api("get", reverse("stars:api_kid", args=[ref])).json()
            self.assertEqual(data["balance"], 2)
            self.assertEqual(data["transactions"][0]["reason"], "dishes")
        self.assertEqual(self.api("get", reverse("stars:api_kid", args=["nobody"])).status_code, 404)

    def test_add_and_remove_stars(self):
        url = reverse("stars:api_stars", args=["Allie"])
        resp = self.api("post", url, {"delta": 5, "reason": "Read a book"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["balance"], 5)
        resp = self.api("post", url, {"delta": -2})
        self.assertEqual(resp.json()["balance"], 3)
        self.assertEqual(self.allie.balance, 3)

    def test_add_stars_validation(self):
        url = reverse("stars:api_stars", args=["Allie"])
        for body in [{}, {"delta": 0}, {"delta": "3"}, {"delta": 1.5}, {"delta": True},
                     {"delta": 1, "reason": 7}, {"delta": 1, "reason": "x" * 256}, [1]]:
            self.assertEqual(self.api("post", url, body).status_code, 400, body)
        resp = self.client.post(url, "not json", content_type="application/json",
                                HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.allie.transactions.count(), 0)

    def test_delete_transaction(self):
        txn = StarTransaction.objects.create(kid=self.allie, delta=4)
        resp = self.api("delete", reverse("stars:api_transaction", args=[txn.id]))
        self.assertEqual(resp.json(), {"deleted": txn.id, "balance": 0})
        resp = self.api("delete", reverse("stars:api_transaction", args=[txn.id]))
        self.assertEqual(resp.status_code, 404)

    def test_wrong_method(self):
        self.assertEqual(self.api("post", reverse("stars:api_kids"), {}).status_code, 405)
        self.assertEqual(self.api("get", reverse("stars:api_stars", args=["Allie"])).status_code, 405)

    def test_create_api_token_command(self):
        out = StringIO()
        call_command("create_api_token", "Home Assistant", stdout=out)
        key = out.getvalue().strip().splitlines()[-1]
        url = reverse("stars:api_kids")
        self.assertEqual(self.api("get", url, key=key).status_code, 200)
