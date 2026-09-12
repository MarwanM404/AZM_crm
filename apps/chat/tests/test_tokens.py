"""The visitor token — their only credential, so its properties are worth pinning."""

from django.core import signing

from apps.chat.services import tokens


def test_a_token_names_the_conversation_it_was_issued_for():
    assert tokens.read(tokens.issue(42)) == 42


def test_a_tampered_token_is_refused_rather_than_raising():
    """An invalid token is an ordinary event — an old tab, an ended conversation — so callers
    refuse the connection rather than handling an exception on every frame."""
    assert tokens.read(tokens.issue(42) + "x") is None
    assert tokens.read("not-a-token") is None
    assert tokens.read("") is None
    assert tokens.read(None) is None


def test_an_expired_token_is_refused(settings):
    settings.CHAT_TOKEN_MAX_AGE_SECONDS = -1
    assert tokens.read(tokens.issue(42)) is None


def test_a_token_for_one_conversation_does_not_open_another():
    """The reason it names a conversation rather than a person: a leaked token exposes one
    conversation, not a visitor's whole history."""
    assert tokens.read(tokens.issue(1)) != 2


def test_the_stored_form_is_a_hash_not_the_token():
    token = tokens.issue(42)
    stored = tokens.fingerprint(token)

    assert stored != token
    assert token not in stored
    assert len(stored) == 64


def test_matching_compares_against_the_hash():
    token = tokens.issue(42)
    assert tokens.matches(token, tokens.fingerprint(token)) is True
    assert tokens.matches(tokens.issue(43), tokens.fingerprint(token)) is False
    assert tokens.matches("", tokens.fingerprint(token)) is False


def test_a_token_cannot_be_forged_without_the_signing_key(settings):
    forged = signing.dumps({"conversation": 99}, salt="a-different-salt")
    assert tokens.read(forged) is None
