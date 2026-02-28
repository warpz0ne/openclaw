# Slice Google Auth Setup (dudda.cloud)

## 1) Google Cloud OAuth (Web client)
Create OAuth Client ID of type **Web application** in the same Google Cloud project.

Set:
- Authorized JavaScript origins:
  - `https://dudda.cloud`
  - `https://www.dudda.cloud` (optional)

Copy the resulting **Client ID**.

## 2) Server env
Edit `/etc/default/slice`:

```bash
sudo nano /etc/default/slice
```

Set:

```bash
GOOGLE_CLIENT_ID=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
ALLOWED_EMAILS=girgitley@gmail.com
SESSION_SECURE=1
```

## 3) Restart app

```bash
sudo systemctl restart slice.service
sudo systemctl status --no-pager slice.service | sed -n '1,30p'
```

## 4) Verify
- Visit `https://dudda.cloud`
- Should redirect to `/login`
- Google login succeeds for allowed email
- Dashboard loads (Finance/News tabs)
- Logout returns to `/login`

## Troubleshooting
- `Server misconfigured: GOOGLE_CLIENT_ID is required`:
  - Missing or empty `GOOGLE_CLIENT_ID` in `/etc/default/slice`
- `Invalid audience` on login:
  - Wrong OAuth Client ID configured (must be the Web client, not Desktop)
- Google popup blocked:
  - Allow popups for `dudda.cloud`
