from .models import StarRequest
from .roles import is_parent, kid_for


def roles(request):
    """Adds is_parent, own_kid and pending_request_count to every template."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"is_parent": False, "own_kid": None, "pending_request_count": 0}
    parent = is_parent(user)
    return {
        "is_parent": parent,
        "own_kid": kid_for(user),
        "pending_request_count": (
            StarRequest.objects.filter(status=StarRequest.PENDING).count() if parent else 0
        ),
    }
