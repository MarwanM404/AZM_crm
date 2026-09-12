# Email setup — what to ask IT for

The support desk needs to send replies to customers and receive their replies back onto the
same ticket. The application side is built and tested; what is missing is a mail domain and a
route, which IT controls (see [ADR-006](decisions/006-deployment-target.md)).

This page is written to be handed over as-is.

---

## What the system needs, in plain terms

1. **An address it can send from**, e.g. `support@yourdomain.com`.
2. **A way for replies to come back**, addressed to `support+AZM-2026-000123@yourdomain.com` —
   the part after the `+` is the ticket number, which is how a reply finds its ticket.
3. **Somewhere to deliver those replies**, either to a mailbox we read, or by the mail provider
   sending them to us directly.

Point 2 matters more than it looks. Most mail systems support "plus addressing" already —
anything sent to `support+anything@` arrives at `support@`. If yours does not, please say so,
because the fallback methods are less reliable.

---

## Two ways to do it — either is fine

### Option A — a mail provider sends replies to us (recommended)

A transactional mail provider (Postmark, Mailgun, SendGrid) handles both directions. When a
customer replies, the provider posts the message to a URL on our server immediately.

**What we need from you**
- A subdomain we can use for mail, e.g. `support.yourdomain.com`, and the ability to add DNS
  records to it: MX, SPF, DKIM, and DMARC.
- Confirmation of which provider is acceptable to the organization.

**Why we suggest it**: replies appear on the ticket within seconds; the provider deals with
spam scoring, bounces and deliverability, which is otherwise ongoing work for your team.

### Option B — we read a mailbox you already have

We poll an ordinary mailbox on a schedule and pull in anything new.

**What we need from you**
- A dedicated mailbox, e.g. `support@yourdomain.com`, that only this system reads.
- IMAP access to it: hostname, port, username, and a password — ideally an app password
  scoped to this mailbox rather than a staff member's own credentials.
- Confirmation that plus-addressing to that mailbox works.

**What it costs**: replies appear on the ticket on the polling interval rather than instantly,
and deliverability of outgoing mail remains your mail server's responsibility.

---

## Sending, either way

- An SMTP host, port, username and password for the sending address, **or** the provider's
  sending credentials if Option A.
- Please confirm the sending address may use a `Reply-To` of
  `support+<ticket-number>@yourdomain.com`. Nothing else about the address changes.

---

## For whoever configures the application

All of this is read from the environment; none of it is committed. Put the values in `.env`:

```bash
# Sending
EMAIL_HOST=smtp.yourprovider.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=support@yourdomain.com
SUPPORT_EMAIL_DOMAIN=yourdomain.com        # the domain used in the Reply-To token

# Receiving — Option A
INBOUND_EMAIL_MODE=webhook
INBOUND_EMAIL_WEBHOOK_SECRET=              # generate a long random value; give it to the provider

# Receiving — Option B
INBOUND_EMAIL_MODE=imap
INBOUND_EMAIL_HOST=imap.yourprovider.com
INBOUND_EMAIL_USER=support@yourdomain.com
INBOUND_EMAIL_PASSWORD=
```

Leaving `INBOUND_EMAIL_MODE` empty switches inbound collection off cleanly — the system runs,
it simply does not collect replies. That is the current state.

**Option A** additionally needs the provider pointed at `POST https://<our-host>/email/inbound/`,
sending the header `X-Webhook-Secret` with the value of `INBOUND_EMAIL_WEBHOOK_SECRET`. The
endpoint refuses anything without a matching secret, and refuses everything if the secret is
unset — it fails closed rather than accepting anonymous mail.

**Option B** needs the Celery beat schedule to run `collect_inbound_email`. Messages are marked
as read only after they are safely stored, so a crash mid-batch redelivers rather than losing
mail.

---

## How a reply finds its ticket

Four rules, tried in order, so a more reliable signal wins when two disagree:

1. The `support+AZM-2026-000123@` address — survives mail clients that rewrite subject lines.
2. The `In-Reply-To` / `References` headers — standard threading.
3. A ticket number quoted in the subject — last resort, because customers edit subjects.
4. No match — a new ticket is created rather than the message being dropped.

Whichever rule matched is recorded against every received message, so if something lands on the
wrong ticket it can be diagnosed rather than guessed at.

---

## One thing to flag

Until this is set up, an agent can write a reply and the system will record it on the ticket,
but **nothing is actually delivered to the customer**. That is the single remaining gap between
the current build and the specification's definition of done.
