"""
Outbound message policy (FR-035).

The one place that decides which language a customer is written to. Kept out of the task so
the rule can be tested directly and so every outbound path — reply, confirmation, and the
channels that arrive after the MVP — answers the question the same way.
"""

DEFAULT_LANGUAGE = "ar"
SUPPORTED = {"ar", "en"}


def language_for_contact(contact) -> str:
    """The contact's recorded preference, falling back to Arabic when it is unknown.

    Arabic rather than English is the fallback deliberately: the organization's customers are
    Arabic-speaking by default, so an unknown preference is far more likely to be Arabic than
    English. Getting this backwards writes to people in a language they may not read.
    """
    preferred = (getattr(contact, "preferred_language", "") or "").strip().lower()
    return preferred if preferred in SUPPORTED else DEFAULT_LANGUAGE
