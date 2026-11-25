from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Kid, QuickAction, StarRequest, StarTransaction
from .roles import is_parent, kid_for, parent_required

# Largest number of stars a kid can ask for in one request.
MAX_REQUEST_STARS = 100


def kid_list(request):
    own_kid = kid_for(request.user)
    if own_kid is not None:
        # Kids land on their own page.
        return redirect(own_kid)
    kids = Kid.objects.all()
    return render(request, "stars/kid_list.html", {"kids": kids})


def kid_detail(request, kid_id):
    kid = get_object_or_404(Kid, pk=kid_id)
    transactions = kid.transactions.all()
    quick_actions = QuickAction.objects.all()

    celebrate = 0
    try:
        celebrate = max(0, int(request.GET.get("celebrate", "0")))
    except ValueError:
        celebrate = 0

    lost = "lost" in request.GET
    is_own_page = kid_for(request.user) == kid

    return render(
        request,
        "stars/kid_detail.html",
        {
            "is_own_page": is_own_page,
            "request_actions": QuickAction.objects.filter(delta__gt=0) if is_own_page else [],
            "max_request_stars": MAX_REQUEST_STARS,
            "kid_requests": (
                kid.requests.filter(status=StarRequest.PENDING)
                if is_own_page or is_parent(request.user)
                else []
            ),
            "kid": kid,
            "transactions": transactions,
            "quick_actions": quick_actions,
            "celebrate": celebrate,
            "lost": lost,
            "balance_before": kid.balance - celebrate,
        },
    )


def _redirect_to_kid(kid, delta=0):
    url = reverse("stars:kid_detail", args=[kid.id])
    if delta > 0:
        url = f"{url}?celebrate={delta}"
    elif delta < 0:
        url = f"{url}?lost={-delta}"
    return redirect(url)


@parent_required
@require_POST
def add_stars(request, kid_id):
    kid = get_object_or_404(Kid, pk=kid_id)
    direction = request.POST.get("direction", "add")
    reason = request.POST.get("reason", "").strip()

    try:
        amount = int(request.POST.get("amount", "").strip())
    except (TypeError, ValueError):
        messages.error(request, "Please enter a whole number of stars.")
        return redirect("stars:kid_detail", kid_id=kid.id)

    if amount <= 0:
        messages.error(request, "Amount must be a positive number.")
        return redirect("stars:kid_detail", kid_id=kid.id)

    delta = amount if direction == "add" else -amount
    StarTransaction.objects.create(kid=kid, delta=delta, reason=reason)
    return _redirect_to_kid(kid, delta=delta)


@parent_required
@require_POST
def quick_action(request, kid_id, action_id):
    kid = get_object_or_404(Kid, pk=kid_id)
    action = get_object_or_404(QuickAction, pk=action_id)
    StarTransaction.objects.create(kid=kid, delta=action.delta, reason=action.label)
    return _redirect_to_kid(kid, delta=action.delta)


@parent_required
@require_POST
def delete_transaction(request, kid_id, txn_id):
    kid = get_object_or_404(Kid, pk=kid_id)
    txn = get_object_or_404(StarTransaction, pk=txn_id, kid=kid)
    txn.delete()
    return redirect("stars:kid_detail", kid_id=kid.id)


# Taps on the quick-tap page within this window of the previous tap are merged
# into a single ledger entry.
TAP_CHUNK_WINDOW = timedelta(seconds=60)


@parent_required
def quick_tap(request):
    return render(request, "stars/quick_tap.html", {"kids": Kid.objects.all()})


@parent_required
@require_POST
def tap(request, kid_id):
    """Add or remove one star, merging into the kid's latest entry if that
    entry has the same reason and was touched within TAP_CHUNK_WINDOW."""
    kid = get_object_or_404(Kid, pk=kid_id)
    step = 1 if request.POST.get("direction", "add") == "add" else -1
    reason = request.POST.get("reason", "").strip()[:255]

    with transaction.atomic():
        latest = (
            StarTransaction.objects.select_for_update()
            .filter(kid=kid)
            .order_by("-created_at", "-id")
            .first()
        )
        cutoff = timezone.now() - TAP_CHUNK_WINDOW
        if (
            latest is not None
            and latest.reason == reason
            and (latest.updated_at or latest.created_at) >= cutoff
        ):
            latest.delta += step
            if latest.delta == 0:
                # Taps cancelled out (e.g. +1 then -1); drop the empty entry.
                latest.delete()
                chunk = 0
            else:
                latest.save(update_fields=["delta", "updated_at"])
                chunk = latest.delta
        else:
            StarTransaction.objects.create(kid=kid, delta=step, reason=reason)
            chunk = step

    return JsonResponse({"kid": kid.id, "balance": kid.balance, "chunk": chunk})


@require_POST
def request_stars(request, kid_id):
    """A kid asks for stars, either for a listed activity or a custom one."""
    kid = get_object_or_404(Kid, pk=kid_id)
    if kid_for(request.user) != kid:
        return HttpResponseForbidden("You can only request stars for yourself.")

    action_id = request.POST.get("action")
    if action_id:
        action = get_object_or_404(QuickAction, pk=action_id, delta__gt=0)
        delta, reason = action.delta, action.label
    else:
        reason = request.POST.get("reason", "").strip()[:255]
        try:
            delta = int(request.POST.get("amount", "").strip())
        except ValueError:
            delta = 0
        if not reason:
            messages.error(request, "Please say what the stars are for.")
            return redirect(kid)
        if not 1 <= delta <= MAX_REQUEST_STARS:
            messages.error(request, f"Ask for between 1 and {MAX_REQUEST_STARS} stars.")
            return redirect(kid)

    StarRequest.objects.create(kid=kid, delta=delta, reason=reason)
    messages.success(request, f"Asked for {delta} star{'s' if delta != 1 else ''}. A parent will check it soon!")
    return redirect(kid)


@require_POST
def cancel_request(request, request_id):
    star_request = get_object_or_404(StarRequest, pk=request_id, status=StarRequest.PENDING)
    if kid_for(request.user) != star_request.kid:
        return HttpResponseForbidden("You can only cancel your own requests.")
    star_request.delete()
    return redirect(star_request.kid)


@parent_required
def request_list(request):
    return render(
        request,
        "stars/requests.html",
        {
            "pending": StarRequest.objects.filter(status=StarRequest.PENDING)
            .select_related("kid")
            .order_by("created_at"),
            "recent": StarRequest.objects.exclude(status=StarRequest.PENDING)
            .select_related("kid", "decided_by")
            .order_by("-decided_at")[:20],
        },
    )


@parent_required
@require_POST
def decide_request(request, request_id, decision):
    with transaction.atomic():
        star_request = get_object_or_404(
            StarRequest.objects.select_for_update(), pk=request_id, status=StarRequest.PENDING
        )
        if decision == "approve":
            star_request.status = StarRequest.APPROVED
            star_request.transaction = StarTransaction.objects.create(
                kid=star_request.kid, delta=star_request.delta, reason=star_request.reason
            )
        else:
            star_request.status = StarRequest.DENIED
        star_request.decided_at = timezone.now()
        star_request.decided_by = request.user
        star_request.save()

    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("stars:request_list")
