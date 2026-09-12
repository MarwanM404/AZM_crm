"""
The visitor's credential (FR-005, research.md #5).

A visitor is anonymous — there is no session to authenticate, and there will not be until the
customer portal. So the token *is* the authorization, and it is scoped deliberately narrowly:
it names one conversation rather than identifying a person, because identity here is only an
email address someone typed into a form.

Signed rather than random, so it can carry an expiry and be verified without a database round
trip on every frame. Stored hashed, never in readable form: the conversation table would
otherwise be a list of live session keys, readable by anyone with database access and retained
as long as the row.
"""

import hashlib

from django.conf import settings
from django.core import signing

SALT = "chat.visitor-token"


def issue(conversation_id) -> str:
    """A token naming exactly one conversation."""
    return signing.dumps({"conversation": int(conversation_id)}, salt=SALT)


def read(token: str):
    """The conversation id this token names, or None when it is invalid or expired.

    Never raises: an invalid token is an ordinary event — an old browser tab, a conversation
    that ended — and the caller refuses the connection rather than handling an exception.
    """
    if not token:
        return None
    max_age = getattr(settings, "CHAT_TOKEN_MAX_AGE_SECONDS", 60 * 60 * 12)
    try:
        payload = signing.loads(token, salt=SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    conversation_id = payload.get("conversation")
    return int(conversation_id) if conversation_id is not None else None


def fingerprint(token: str) -> str:
    """What gets stored. A hash, so the column cannot be used as a set of session keys."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def matches(token: str, stored_hash: str) -> bool:
    import hmac

    return bool(token) and hmac.compare_digest(fingerprint(token), stored_hash or "")
