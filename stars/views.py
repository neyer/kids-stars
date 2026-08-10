from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Kid, QuickAction, StarTransaction


def kid_list(request):
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

    return render(
        request,
        "stars/kid_detail.html",
        {
            "kid": kid,
            "transactions": transactions,
            "quick_actions": quick_actions,
            "celebrate": celebrate,
            "balance_before": kid.balance - celebrate,
        },
    )


def _redirect_to_kid(kid, celebrate_delta=0):
    url = reverse("stars:kid_detail", args=[kid.id])
    if celebrate_delta > 0:
        url = f"{url}?celebrate={celebrate_delta}"
    return redirect(url)


@login_required
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
    return _redirect_to_kid(kid, celebrate_delta=delta if delta > 0 else 0)


@login_required
@require_POST
def quick_action(request, kid_id, action_id):
    kid = get_object_or_404(Kid, pk=kid_id)
    action = get_object_or_404(QuickAction, pk=action_id)
    StarTransaction.objects.create(kid=kid, delta=action.delta, reason=action.label)
    return _redirect_to_kid(kid, celebrate_delta=action.delta if action.delta > 0 else 0)


@login_required
@require_POST
def delete_transaction(request, kid_id, txn_id):
    kid = get_object_or_404(Kid, pk=kid_id)
    txn = get_object_or_404(StarTransaction, pk=txn_id, kid=kid)
    txn.delete()
    return redirect("stars:kid_detail", kid_id=kid.id)
