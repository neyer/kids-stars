"""JSON API for other apps to read balances and add or remove stars.

Every request needs an API token:  Authorization: Bearer <key>
Create one with `python3 manage.py create_api_token "<app name>"` or in the
admin site under "Api tokens".
"""

import json
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import ApiToken, Kid, StarTransaction, hash_token

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def _error(status, message):
    return JsonResponse({"error": message}, status=status)


def token_required(view):
    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, key = header.partition(" ")
        if scheme.lower() != "bearer" or not key.strip():
            return _error(401, "Missing API token. Send 'Authorization: Bearer <key>'.")
        token = ApiToken.objects.filter(key_hash=hash_token(key.strip()), active=True).first()
        if token is None:
            return _error(401, "Invalid or revoked API token.")
        ApiToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
        request.api_token = token
        return view(request, *args, **kwargs)

    return wrapper


def _find_kid(kid_ref):
    """Look a kid up by id, or by name (case-insensitive)."""
    if kid_ref.isdigit():
        return Kid.objects.filter(pk=int(kid_ref)).first()
    return Kid.objects.filter(name__iexact=kid_ref).first()


def _kid_json(kid):
    return {
        "id": kid.id,
        "name": kid.name,
        "balance": kid.balance,
        "pending_stars": kid.pending_stars,
    }


def _txn_json(txn):
    return {
        "id": txn.id,
        "kid": txn.kid_id,
        "delta": txn.delta,
        "reason": txn.reason,
        "created_at": txn.created_at.isoformat(),
    }


@token_required
def kids(request):
    if request.method != "GET":
        return _error(405, "Use GET.")
    return JsonResponse({"kids": [_kid_json(k) for k in Kid.objects.all()]})


@token_required
def kid_detail(request, kid_ref):
    if request.method != "GET":
        return _error(405, "Use GET.")
    kid = _find_kid(kid_ref)
    if kid is None:
        return _error(404, f"No kid '{kid_ref}'.")
    try:
        limit = min(max(int(request.GET.get("limit", DEFAULT_LIMIT)), 0), MAX_LIMIT)
    except ValueError:
        return _error(400, "'limit' must be a whole number.")
    data = _kid_json(kid)
    data["transactions"] = [_txn_json(t) for t in kid.transactions.all()[:limit]]
    return JsonResponse(data)


@token_required
def stars(request, kid_ref):
    """POST {"delta": 3, "reason": "..."} to add stars; a negative delta removes them."""
    if request.method != "POST":
        return _error(405, "Use POST.")
    kid = _find_kid(kid_ref)
    if kid is None:
        return _error(404, f"No kid '{kid_ref}'.")
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error(400, "Body must be JSON.")
    if not isinstance(body, dict):
        return _error(400, "Body must be a JSON object.")

    delta = body.get("delta")
    if isinstance(delta, bool) or not isinstance(delta, int) or delta == 0:
        return _error(400, "'delta' must be a non-zero whole number.")
    reason = body.get("reason", "")
    if not isinstance(reason, str):
        return _error(400, "'reason' must be a string.")
    reason = reason.strip()
    if len(reason) > 255:
        return _error(400, "'reason' must be 255 characters or fewer.")

    txn = StarTransaction.objects.create(kid=kid, delta=delta, reason=reason)
    return JsonResponse({"transaction": _txn_json(txn), "balance": kid.balance}, status=201)


@token_required
def transaction_detail(request, txn_id):
    """DELETE a transaction to undo it."""
    if request.method != "DELETE":
        return _error(405, "Use DELETE.")
    txn = StarTransaction.objects.filter(pk=txn_id).first()
    if txn is None:
        return _error(404, f"No transaction {txn_id}.")
    kid = txn.kid
    txn.delete()
    return JsonResponse({"deleted": txn_id, "balance": kid.balance})
