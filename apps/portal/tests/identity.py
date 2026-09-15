"""
Comparing two responses for what they disclose (FR-007).

FR-007 says the answer must be identical whether or not an address is known, and the obvious
test — compare the bytes — fails on two things that disclose nothing:

  * the CSRF token, which is fresh per response and is supposed to be;
  * the address itself, echoed back into the form, which the person reading typed.

Masking both leaves the part the requirement is actually about: the message. A softer
comparison than bytes would have been easier and would have let through a changed status
code, an extra field, or a single different word — which is all an attacker needs.
"""

import re

CSRF = re.compile(r'(csrfmiddlewaretoken" value="|X-CSRFToken": ")[^"]+')


def comparable(response, *masked):
    body = response.content.decode()
    body = CSRF.sub(r"\1[CSRF]", body)
    for value in masked:
        body = body.replace(value, "[MASKED]")
    return body
