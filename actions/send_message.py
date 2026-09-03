"""
send_message.py — Discord, Telegram, Email and SMS gateways for JARVIS.
"""
from __future__ import annotations

import os
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Optional

from config import get_config


def _cfg(key: str) -> Optional[str]:
    return get_config().get(key) or os.environ.get(key.upper())


def _http_post_json(url: str, payload: dict, headers: Optional[dict] = None,
                    timeout: int = 15) -> tuple[bool, dict]:
    import json
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     **(headers or {})},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode("utf-8"))
        except Exception:
            return False, {"error": str(e)}
    except Exception as e:
        return False, {"error": str(e)}


class SendMessage:
    """Cross-platform message dispatch."""

    # ── Discord ─────────────────────────────────────────────────────────────

    def send_discord(self, channel: str, message: str,
                     username: str = "JARVIS") -> tuple[bool, str]:
        """
        `channel` may be either a webhook URL or a channel ID (requires a bot
        token in config: discord_bot_token).
        """
        if not channel:
            return False, "No channel provided"

        if channel.startswith("http"):
            # webhook
            ok, body = _http_post_json(channel, {"content": message, "username": username})
            return ok, json.dumps(body) if False else (body.get("message", "sent") if ok else str(body))

        # bot-based channel post
        token = _cfg("discord_bot_token")
        if not token:
            return False, "No discord_bot_token in config"
        url = f"https://discord.com/api/v10/channels/{channel}/messages"
        ok, body = _http_post_json(
            url, {"content": message},
            headers={"Authorization": f"Bot {token}"},
        )
        return ok, "sent" if ok else str(body)

    # ── Telegram ───────────────────────────────────────────────────────────

    def send_telegram(self, chat_id: str, message: str,
                      parse_mode: str = "HTML") -> tuple[bool, str]:
        token = _cfg("telegram_bot_token")
        if not token:
            return False, "No telegram_bot_token in config"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        ok, body = _http_post_json(url, {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        })
        return ok, "sent" if ok else str(body)

    # ── Email ──────────────────────────────────────────────────────────────

    def send_email(self, to: str, subject: str, body: str,
                   smtp_host: Optional[str] = None,
                   smtp_port: Optional[int] = None,
                   username: Optional[str] = None,
                   password: Optional[str] = None,
                   from_addr: Optional[str] = None) -> tuple[bool, str]:
        smtp_host = smtp_host or _cfg("smtp_host") or "smtp.gmail.com"
        smtp_port = smtp_port or int(_cfg("smtp_port") or 587)
        username  = username or _cfg("smtp_username") or _cfg("email_address")
        password  = password or _cfg("smtp_password") or _cfg("email_app_password")
        from_addr = from_addr or _cfg("email_from") or username

        if not (username and password and to):
            return False, "Missing smtp credentials or recipient"

        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as s:
                s.ehlo()
                s.starttls()
                s.login(username, password)
                s.send_message(msg)
            return True, "sent"
        except Exception as e:
            return False, f"smtp error: {e}"

    # ── SMS (Twilio) ───────────────────────────────────────────────────────

    def send_sms(self, phone: str, message: str) -> tuple[bool, str]:
        """
        Twilio REST API.
        Reads twilio_account_sid, twilio_auth_token, twilio_from from config.
        """
        sid    = _cfg("twilio_account_sid")
        token  = _cfg("twilio_auth_token")
        sender = _cfg("twilio_from")

        if not (sid and token and sender):
            return False, "Missing Twilio config (twilio_account_sid/_auth_token/_from)"

        import base64
        import json as _json
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        body = urllib.parse.urlencode({"To": phone, "From": sender, "Body": message})
        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        try:
            req = urllib.request.Request(
                url, data=body.encode(),
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                payload = _json.loads(r.read().decode())
            return True, payload.get("sid", "sent")
        except urllib.error.HTTPError as e:
            try:
                err_body = _json.loads(e.read().decode())
            except Exception:
                err_body = {"error": str(e)}
            return False, str(err_body)
        except Exception as e:
            return False, f"twilio error: {e}"