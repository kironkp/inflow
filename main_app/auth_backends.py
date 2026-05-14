"""Custom auth backend: log in by either username OR email.

Login is the only place this kicks in. Existing username-based code paths
(shares, ownership checks, etc.) are unaffected because Django's User model
still has a username — the backend just adds an alternate lookup key.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        ident = username.strip()
        # Try email first if it looks like one; otherwise try username first.
        # Either way, fall through to the other lookup so users can type
        # whichever is handier.
        candidates = []
        if '@' in ident:
            candidates = [{'email__iexact': ident}, {'username__iexact': ident}]
        else:
            candidates = [{'username__iexact': ident}, {'email__iexact': ident}]
        for lookup in candidates:
            try:
                user = User.objects.get(**lookup)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                continue
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
