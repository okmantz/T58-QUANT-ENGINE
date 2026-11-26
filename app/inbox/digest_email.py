"""Weekly digest email: render, deliver, schedule, and the opt-out preference.

Flow
  * A small background thread wakes every 20 minutes. From Sunday 08:00 (local) it builds the week's digest, makes sure the in-app
    inbox copy exists, and emails it once for that week. A missed Sunday is caught up the next time the app is open.
  * Recipient = the email the person logs in with (license email, falling back to the account email). Nothing else is ever emailed.
  * Delivery: the license server relays it (POST /v1/digest/send, authenticated with the same email + license key + device id as
    every other license call), so customers never configure SMTP. If the server is unreachable, a locally configured SMTP account
    (Settings -> notifications) is used as a fallback. Master keys have no server account, so they use the local fallback only.
  * Opt-out: data/config/digest_prefs.json {"enabled": true}. Default is ON. Turning it off stops the email; the in-app bell
    message is unaffected.
"""
from __future__ import annotations

import html
import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
CHECK_EVERY_S = 20 * 60
MAX_TRIES_PER_WEEK = 8
RETRY_AFTER_S = 6 * 3600


# ------------------------------------------------------------------------------------------------------------ preferences
def _prefs_path() -> Path:
    from app.data.storage import get_app_base_dir
    p = get_app_base_dir() / "data" / "config" / "digest_prefs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_prefs() -> dict[str, Any]:
    d: dict[str, Any] = {}
    try:
        raw = json.loads(_prefs_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            d = raw
    except Exception:  # noqa: BLE001
        pass
    return {"enabled": bool(d.get("enabled", True)), "last_sent_key": str(d.get("last_sent_key") or ""), "last_sent_at": float(d.get("last_sent_at") or 0),
            "tries": d.get("tries") if isinstance(d.get("tries"), dict) else {}, "last_error": str(d.get("last_error") or "")}


def save_prefs(**changes: Any) -> dict[str, Any]:
    with _LOCK:
        d = load_prefs()
        d.update(changes)
        p = _prefs_path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
        tmp.replace(p)
        return d


def is_enabled() -> bool:
    return bool(load_prefs()["enabled"])


# ------------------------------------------------------------------------------------------------------------ recipient / transport
def recipient_email() -> str:
    try:
        from app.persistence import vault
        return vault.account_email() or ""
    except Exception:  # noqa: BLE001
        return ""


def _creds() -> tuple[str, str, str]:
    try:
        from app.licensing import client
        st = client.load_state()
        return (st.email or "").strip(), (st.license_key or "").strip(), (st.device_id or "").strip()
    except Exception:  # noqa: BLE001
        return "", "", ""


def _is_master() -> bool:
    try:
        from app.licensing import client
        return bool(client._is_master_key(_creds()[1]))
    except Exception:  # noqa: BLE001
        return False


def _relay_possible() -> bool:
    email, key, dev = _creds()
    if not (email and key and dev) or _is_master():
        return False
    try:
        from app.persistence import vault
        return bool(vault._server_base())
    except Exception:  # noqa: BLE001
        return False


def _local_smtp_usable() -> bool:
    try:
        from app.web.notifications import load_notification_settings
        return bool(load_notification_settings().is_usable)
    except Exception:  # noqa: BLE001
        return False


def delivery_route() -> str | None:
    """'relay' (license server), 'smtp' (their own SMTP settings) or None when neither is available."""
    if _relay_possible():
        return "relay"
    if _local_smtp_usable():
        return "smtp"
    return None


def _send_via_relay(subject: str, body_html: str, body_text: str) -> tuple[bool, str]:
    from app.persistence import vault
    email, key, dev = _creds()
    ok, body, err = vault._cloud_call("/v1/digest/send", {"email": email, "license_key": key, "device_id": dev, "subject": subject, "html": body_html, "text": body_text}, timeout=30.0)
    if not ok:
        return False, err or "Could not reach the license server."
    if body.get("ok"):
        return True, ""
    code = str(body.get("error") or "failed")
    msg = {"server_too_old": "The license server does not have the digest relay yet; redeploy license_server/ from this update.",
           "smtp_not_configured": "The license server has no mail account configured (SMTP_HOST/USER/PASS).",
           "rate_limited": "Too many digest emails sent recently. Try again tomorrow."}.get(code, body.get("message") or code)
    return False, str(msg)


def _send_via_smtp(to: str, subject: str, body_html: str, body_text: str) -> tuple[bool, str]:
    import smtplib
    from email.message import EmailMessage
    from app.web.notifications import load_notification_settings
    s = load_notification_settings()
    if not s.is_usable:
        return False, "No email account is configured."
    em = EmailMessage()
    em["Subject"], em["From"], em["To"] = subject, s.smtp_from.strip(), to
    em.set_content(body_text)
    em.add_alternative(body_html, subtype="html")
    try:
        with smtplib.SMTP(s.smtp_host.strip(), int(s.smtp_port or 587), timeout=20) as srv:
            srv.starttls()
            if s.smtp_username.strip():
                srv.login(s.smtp_username.strip(), s.smtp_password)
            srv.send_message(em)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"Email send failed: {exc}"


def deliver(dg: dict[str, Any]) -> tuple[bool, str]:
    to = recipient_email()
    if not to:
        return False, "No email address is on file for this account."
    subject, h, t = render(dg, to)
    last = "No way to send email from this install."
    if _relay_possible():
        ok, last = _send_via_relay(subject, h, t)
        if ok:
            return True, "Sent to " + to
    if _local_smtp_usable():
        ok, why = _send_via_smtp(to, subject, h, t)
        if ok:
            return True, "Sent to " + to
        last = why
    return False, last


# ------------------------------------------------------------------------------------------------------------ schedule
def due_anchor(now: float | None = None) -> tuple[str, float]:
    """(week key, anchor timestamp): the most recent Sunday 08:00 local that is <= now."""
    now = now or time.time()
    dt = datetime.fromtimestamp(now)
    sun = dt - timedelta(days=(dt.weekday() + 1) % 7)
    anchor = sun.replace(hour=8, minute=0, second=0, microsecond=0)
    if anchor.timestamp() > now:
        anchor -= timedelta(days=7)
    return "weekly-" + anchor.strftime("%Y-%m-%d"), anchor.timestamp()


def send_due_digest(now: float | None = None, force: bool = False) -> dict[str, Any]:
    """Send this week's email if it is due. force=True is the 'send me a test' path (ignores the schedule and opt-out, never marks the week as sent)."""
    from app import inbox
    now = now or time.time()
    key, _ = due_anchor(now)
    prefs = load_prefs()
    if not force:
        if not prefs["enabled"]:
            return {"sent": False, "reason": "opted_out"}
        if prefs["last_sent_key"] == key:
            return {"sent": False, "reason": "already_sent"}
        tr = prefs["tries"].get(key) or {"n": 0, "at": 0}
        if tr["n"] >= MAX_TRIES_PER_WEEK or (tr["n"] and now - float(tr["at"]) < RETRY_AFTER_S):
            return {"sent": False, "reason": "backoff"}
        inst = inbox._load().get("installed_at")
        if not inst:
            d = inbox._load()
            d["installed_at"] = now
            inbox._save(d)
            return {"sent": False, "reason": "fresh_install"}
        if now - float(inst) < 24 * 3600:
            return {"sent": False, "reason": "fresh_install"}
        if not recipient_email() or delivery_route() is None:
            return {"sent": False, "reason": "no_route"}
    dg = inbox.build_weekly_digest(now)
    if not force:
        try:
            inbox.add_message("weekly_digest", dg["title"], dg, key=key)
        except Exception:  # noqa: BLE001
            pass
    ok, msg = deliver(dg)
    if force:
        return {"sent": ok, "message": msg}
    if ok:
        save_prefs(last_sent_key=key, last_sent_at=now, last_error="", tries={})
    else:
        tr = prefs["tries"].get(key) or {"n": 0, "at": 0}
        save_prefs(last_error=msg, tries={key: {"n": int(tr["n"]) + 1, "at": now}})
    return {"sent": ok, "message": msg}


def _loop() -> None:
    time.sleep(90)
    while True:
        try:
            send_due_digest()
        except Exception:  # noqa: BLE001 -- a scheduler hiccup must never touch the app
            pass
        time.sleep(CHECK_EVERY_S)


def start_scheduler() -> None:
    """Idempotent. Skipped under tests (pytest) and when T58_NO_DIGEST=1."""
    global _THREAD
    import sys
    if "pytest" in sys.modules or os.environ.get("T58_NO_DIGEST") == "1":
        return
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return
        _THREAD = threading.Thread(target=_loop, name="t58-weekly-digest", daemon=True)
        _THREAD.start()


def status() -> dict[str, Any]:
    p = load_prefs()
    key, anchor = due_anchor()
    nxt = datetime.fromtimestamp(anchor) + timedelta(days=7)
    return {"enabled": p["enabled"], "email": recipient_email(), "route": delivery_route(), "last_sent_at": p["last_sent_at"] or None,
            "last_error": p["last_error"], "next_send": nxt.strftime("%A %b %d, %Y") + " (morning)"}


# ------------------------------------------------------------------------------------------------------------ rendering
BRAND = "#12b58a"
INK = "#0e1b24"
MUTED = "#5b6b78"


def _e(s: Any) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _app_url() -> str:
    return (os.environ.get("T58_PUBLIC_URL") or "http://localhost:5000").rstrip("/")


def _next_step(dg: dict[str, Any]) -> tuple[str, str, str]:
    """(headline, detail, path): one concrete suggestion computed from the digest itself."""
    ids = {s["id"]: s for s in dg.get("sections", [])}
    st = dg.get("stats") or {}
    if "ready" in ids:
        return ("Promote your front-runner", ids["ready"]["headline"] + ". Open the Champion board to see exactly what it still needs.", "/champion-simple")
    if st.get("failed", 0) and not st.get("passed", 0):
        return ("Learn from the failures", "Every test failed this week. Open the Graveyard to see the pattern before you build the next idea.", "/graveyard")
    if st.get("experiments", 0):
        return ("Stress-test what survived", "You have fresh results. Run Validate on your best strategy before you trust it.", "/validate-simple")
    return ("Start the week with one test", "A quiet week. Pick one strategy, run Test, and let the verdict tell you what to do next.", "/full-pipeline")


def render(dg: dict[str, Any], to: str = "", name: str = "") -> tuple[str, str, str]:
    """(subject, html, text) for a digest dict from inbox.build_weekly_digest()."""
    base = _app_url()
    title = dg.get("title") or "Your week in the lab"
    st = dg.get("stats") or {}
    head, detail, path = _next_step(dg)
    subject = "Your T58 week: " + (f"{st.get('experiments', 0)} experiments" if st.get("experiments") else "a quiet week") + " + what to do next"

    def tile(n: Any, label: str) -> str:
        return (f'<td align="center" width="25%" style="padding:0 5px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f7f6;border-radius:12px">'
                f'<tr><td align="center" style="padding:14px 6px 2px;font:700 26px/1.1 Helvetica,Arial,sans-serif;color:{INK}">{_e(n)}</td></tr>'
                f'<tr><td align="center" style="padding:0 6px 14px;font:600 11px/1.3 Helvetica,Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:{MUTED}">{_e(label)}</td></tr></table></td>')

    tiles = ""
    if any(st.get(k, 0) for k in ("experiments", "passed", "failed", "buried")):
        tiles = ('<tr><td style="padding:6px 25px 4px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
                 + tile(st.get("experiments", 0), "Experiments") + tile(st.get("passed", 0), "Passed") + tile(st.get("failed", 0), "Failed") + tile(st.get("buried", 0), "Buried")
                 + "</tr></table></td></tr>")

    body = ""
    if dg.get("empty"):
        body += (f'<tr><td style="padding:18px 30px 6px;font:400 15px/1.6 Helvetica,Arial,sans-serif;color:{INK}">{_e(dg.get("empty_line", ""))}</td></tr>')
    colors = {"tested": "#2f80ed", "died": "#e5484d", "ready": BRAND}
    for s in dg.get("sections", []):
        col = colors.get(s["id"], BRAND)
        items = "".join(f'<tr><td valign="top" style="padding:3px 10px 3px 0;color:{col};font:700 14px/1.5 Helvetica,Arial,sans-serif">&bull;</td>'
                        f'<td style="padding:3px 0;font:400 14px/1.55 Helvetica,Arial,sans-serif;color:{INK}">{_e(i)}</td></tr>' for i in s.get("items", []))
        body += (f'<tr><td style="padding:16px 25px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e3ebef;border-radius:14px">'
                 f'<tr><td style="padding:16px 20px 4px"><div style="font:800 11px/1 Helvetica,Arial,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:{col}">{_e(s["title"])}</div>'
                 f'<div style="padding-top:8px;font:700 17px/1.35 Helvetica,Arial,sans-serif;color:{INK}">{_e(s["headline"])}</div></td></tr>'
                 f'<tr><td style="padding:6px 20px 16px"><table role="presentation" cellpadding="0" cellspacing="0" width="100%">{items}</table></td></tr></table></td></tr>')

    cta = (f'<tr><td style="padding:22px 25px 6px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{INK};border-radius:16px">'
           f'<tr><td style="padding:22px 24px 6px"><div style="font:800 11px/1 Helvetica,Arial,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:{BRAND}">Your next step</div>'
           f'<div style="padding-top:8px;font:700 19px/1.3 Helvetica,Arial,sans-serif;color:#ffffff">{_e(head)}</div>'
           f'<div style="padding-top:6px;font:400 14px/1.6 Helvetica,Arial,sans-serif;color:#b9c7d0">{_e(detail)}</div></td></tr>'
           f'<tr><td style="padding:14px 24px 24px"><a href="{_e(base + path)}" style="display:inline-block;background:{BRAND};color:#04251c;text-decoration:none;font:700 14px/1 Helvetica,Arial,sans-serif;padding:13px 22px;border-radius:10px">Open T58 &rarr;</a></td></tr></table></td></tr>')

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>{_e(title)}</title></head>
<body style="margin:0;padding:0;background:#eaf0f2">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{_e(head)}. {_e(dg.get("subtitle", ""))}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eaf0f2"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 8px 30px rgba(14,27,36,.10)">
<tr><td style="background:{INK};background-image:linear-gradient(135deg,#0e1b24 0%,#0f3a33 100%);padding:30px 30px 26px">
<div style="font:800 12px/1 Helvetica,Arial,sans-serif;letter-spacing:.2em;color:{BRAND}">T58 QUANT ENGINE</div>
<div style="padding-top:14px;font:800 27px/1.2 Helvetica,Arial,sans-serif;color:#ffffff">{_e(title)}</div>
<div style="padding-top:8px;font:400 14px/1.5 Helvetica,Arial,sans-serif;color:#a9bcc6">{_e(dg.get("subtitle", ""))}</div></td></tr>
<tr><td style="height:6px;background:linear-gradient(90deg,{BRAND},#2f80ed,#8b7cff);font-size:0;line-height:0">&nbsp;</td></tr>
<tr><td style="padding:22px 30px 4px;font:400 15px/1.6 Helvetica,Arial,sans-serif;color:{INK}">{('Hi ' + _e(name) + ',') if name else 'Hi,'} here is your weekly lab report, built only from results saved on your computer.</td></tr>
{tiles}{body}{cta}
<tr><td style="padding:24px 30px 28px;font:400 12px/1.7 Helvetica,Arial,sans-serif;color:{MUTED};border-top:1px solid #eef3f5;margin-top:18px">
Sent every Sunday to {_e(to) if to else 'the email on your account'}. Nothing here is financial advice; it only summarises your own saved results.<br>
Do not want it? Open <b>Account settings &rarr; Notifications &rarr; Weekly digest</b> in T58 and switch it off. You can switch it back on any time.</td></tr>
</table>
<div style="padding:14px 0 0;font:400 11px/1.5 Helvetica,Arial,sans-serif;color:#8a9aa5">T58 Trading &middot; research tool for traders</div>
</td></tr></table></body></html>"""

    lines = [title, "", dg.get("subtitle", ""), ""]
    if st:
        lines.append(f"Experiments {st.get('experiments', 0)} | Passed {st.get('passed', 0)} | Failed {st.get('failed', 0)} | Buried {st.get('buried', 0)}")
        lines.append("")
    if dg.get("empty"):
        lines += [dg.get("empty_line", ""), ""]
    for s in dg.get("sections", []):
        lines.append(f"{s['title'].upper()}: {s['headline']}")
        lines += [f"  - {i}" for i in s.get("items", [])]
        lines.append("")
    lines += [f"YOUR NEXT STEP: {head}", detail, f"Open T58: {base + path}", "", "Turn this email off in Account settings > Notifications > Weekly digest."]
    return subject, doc, "\n".join(lines)
