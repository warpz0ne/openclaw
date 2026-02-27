#!/usr/bin/env python3
import json
import random
import smtplib
import subprocess
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import requests

STATE_PATH = Path('/home/manu/.openclaw/workspace/memory/blossom-slot-state.json')
SECRETS = {
    'user': 'blossom-foundation-username',
    'pass': 'blossom-foundation-password',
    'smtp_host': 'alert-smtp-host',
    'smtp_port': 'alert-smtp-port',
    'smtp_user': 'alert-smtp-user',
    'smtp_pass': 'alert-smtp-pass',
    'email_to': 'alert-email-to',
}
API_BASE = 'https://blossom-api.fly.dev'
WATCH_SKUS = {'KY-SPRING26-1', 'KY-SPRING26-2'}


def get_secret(name: str) -> str:
    out = subprocess.check_output(
        ['gcloud', 'secrets', 'versions', 'access', 'latest', f'--secret={name}'],
        text=True,
    )
    return out.strip()


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        'last_alert_open': False,
        'last_alert_at': None,
        'next_check_after': None,
        'last_checked_at': None,
    }


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def in_window_utc_now_for_et() -> bool:
    out = subprocess.check_output(['bash', '-lc', 'TZ=America/New_York date +%H:%M'], text=True).strip()
    hh, _mm = map(int, out.split(':'))
    return 5 <= hh <= 23  # 5:00 AM through 11:59 PM ET


def fetch_retreats(username: str, password: str):
    s = requests.Session()
    r = s.post(f'{API_BASE}/auth/jwt/login', data={'username': username, 'password': password}, timeout=30)
    r.raise_for_status()
    token = r.json().get('access_token')
    s.headers.update({'Authorization': f'Bearer {token}'})

    rr = s.get(f'{API_BASE}/retreats', timeout=30)
    rr.raise_for_status()
    data = rr.json()

    normalized = []
    for item in data:
        normalized.append({
            'title': item.get('title'),
            'sku': item.get('sku'),
            'has_availability': bool(item.get('has_availability')),
            'is_registration_open': bool(item.get('is_registration_open')),
            'start_date': item.get('start_date'),
            'location': item.get('location'),
        })
    return normalized


def is_open(item):
    return item.get('has_availability') and item.get('is_registration_open')


def render_email_html(checked_at_utc: str, open_any, open_watched):
    def li(item):
        return f"<li><strong>{item['title']}</strong> <span style='color:#666'>(SKU: {item.get('sku','-')})</span></li>"

    if open_any:
        all_open_html = '\n'.join(li(x) for x in open_any)
    else:
        all_open_html = "<li>None open right now</li>"

    if open_watched:
        watched_html = '\n'.join(li(x) for x in open_watched)
        watched_block = f"""
        <div style='padding:10px 12px;border:1px solid #d1fae5;background:#ecfdf5;border-radius:8px;margin-top:12px;'>
          <div style='font-weight:700;color:#065f46;'>⭐ Kriya 1/2 opening detected</div>
          <ul style='margin:8px 0 0 18px;padding:0;'>{watched_html}</ul>
        </div>
        """
    else:
        watched_block = """
        <div style='padding:10px 12px;border:1px solid #e5e7eb;background:#f9fafb;border-radius:8px;margin-top:12px;'>
          <div style='font-weight:700;color:#374151;'>Kriya Yoga 1/2</div>
          <div style='margin-top:4px;color:#4b5563;'>No Kriya 1/2 openings detected in this check.</div>
        </div>
        """

    return f"""
    <html>
      <body style='font-family:Arial,Helvetica,sans-serif;line-height:1.45;color:#111827;'>
        <div style='max-width:620px;margin:0 auto;border:1px solid #e5e7eb;border-radius:10px;padding:16px;'>
          <h2 style='margin:0 0 6px 0;'>Blossom Registration Update</h2>
          <div style='color:#6b7280;font-size:13px;'>Checked at (UTC): {checked_at_utc}</div>

          <h3 style='margin:16px 0 8px 0;'>Currently Open Retreats</h3>
          <ul style='margin:0 0 8px 18px;padding:0;'>
            {all_open_html}
          </ul>

          {watched_block}
        </div>
      </body>
    </html>
    """


def send_email(smtp_host, smtp_port, smtp_user, smtp_pass, to_addr, subject, body_text, body_html):
    msg = EmailMessage()
    msg['From'] = smtp_user
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype='html')

    with smtplib.SMTP(smtp_host, int(smtp_port), timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def main():
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    now_ts = int(now_dt.timestamp())

    if not in_window_utc_now_for_et():
        print(json.dumps({'ok': True, 'skipped': 'outside_window', 'checked_at': now}))
        return

    state = load_state()

    next_check_after = state.get('next_check_after')
    if next_check_after and now_ts < int(next_check_after):
        print(json.dumps({'ok': True, 'skipped': 'not_due_yet', 'checked_at': now, 'next_check_after': next_check_after}))
        return

    time.sleep(random.randint(20, 140))

    username = get_secret(SECRETS['user'])
    password = get_secret(SECRETS['pass'])
    retreats = fetch_retreats(username, password)

    open_any = [x for x in retreats if is_open(x)]
    open_watched = [x for x in open_any if x.get('sku') in WATCH_SKUS]
    alert_triggered = len(open_watched) > 0 and not state.get('last_alert_open', False)

    smtp_host = get_secret(SECRETS['smtp_host'])
    smtp_port = get_secret(SECRETS['smtp_port'])
    smtp_user = get_secret(SECRETS['smtp_user'])
    smtp_pass = get_secret(SECRETS['smtp_pass'])
    email_to = get_secret(SECRETS['email_to'])

    kriya_status = 'OPEN' if open_watched else 'NOT OPEN'
    subject = f'Kriya Yoga 1/2: {kriya_status} | Blossom registration update'
    if open_any:
        subject += ' (spots available)'

    text_lines = [
        f'Checked at (UTC): {now}',
        '',
        'Open retreats now:',
    ]
    if open_any:
        for x in open_any:
            text_lines.append(f"- {x['title']} (SKU: {x.get('sku','-')})")
    else:
        text_lines.append('- None open right now')

    if open_watched:
        text_lines += ['', 'Kriya 1/2 OPEN:']
        for x in open_watched:
            text_lines.append(f"- {x['title']} (SKU: {x.get('sku','-')})")

    body_text = '\n'.join(text_lines)
    body_html = render_email_html(now, open_any, open_watched)

    email_sent = False
    # Alert only when watched Kriya Yoga slots are currently open.
    if open_watched:
        send_email(smtp_host, smtp_port, smtp_user, smtp_pass, email_to, subject, body_text, body_html)
        email_sent = True

    state['last_alert_open'] = len(open_watched) > 0
    if alert_triggered:
        state['last_alert_at'] = now
    state['last_checked_at'] = now
    state['next_check_after'] = now_ts + random.randint(23 * 60, 41 * 60)
    save_state(state)

    print(json.dumps({
        'ok': True,
        'checked_at': now,
        'any_open': len(open_any) > 0,
        'open_items': [{'title': x['title'], 'sku': x.get('sku')} for x in open_any],
        'open_watched_items': [{'title': x['title'], 'sku': x.get('sku')} for x in open_watched],
        'alert_triggered': alert_triggered,
        'email_sent': email_sent,
    }))


if __name__ == '__main__':
    main()
