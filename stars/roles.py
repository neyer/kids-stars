"""Who is allowed to do what.

A logged-in user linked to a Kid is a kid: they can view pages and request
stars for themselves. Any other logged-in user is a parent and can change
balances and approve requests.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

from .models import Kid


def kid_for(user):
    """The Kid linked to this user, or None."""
    if not user.is_authenticated:
        return None
    try:
        return user.kid
    except Kid.DoesNotExist:
        return None


def is_parent(user):
    return user.is_authenticated and kid_for(user) is None


def parent_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_parent(request.user):
            return HttpResponseForbidden("Only parents can do that.")
        return view(request, *args, **kwargs)

    return wrapper
