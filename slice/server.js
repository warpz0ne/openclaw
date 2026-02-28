const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const crypto = require('crypto');
const https = require('https');
const querystring = require('querystring');

const ROOT = path.join(__dirname, 'web');
const PORT = process.env.PORT || 8787;

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID || '';
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET || '';
const GOOGLE_REDIRECT_URI = process.env.GOOGLE_REDIRECT_URI || 'https://dudda.cloud/auth/google/callback';

const SESSION_TTL_MS = 1000 * 60 * 60 * 24 * 7; // 7 days
const SESSION_COOKIE = 'slice_session';
const SESSION_SECURE = process.env.SESSION_SECURE === '1';

const ALLOWED_EMAILS = new Set(
  (process.env.ALLOWED_EMAILS || '')
    .split(',')
    .map(s => s.trim().toLowerCase())
    .filter(Boolean)
);

const sessions = new Map();
const oauthStates = new Map();

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml'
};

function runScript(scriptPath) {
  return new Promise((resolve, reject) => {
    execFile('python3', [scriptPath], { timeout: 120000 }, (err, stdout, stderr) => {
      if (err) return reject(new Error((stderr || err.message || '').toString()));
      resolve((stdout || '').toString().trim());
    });
  });
}

async function refreshDataset(tab) {
  const finance = '/home/manu/.openclaw/workspace/tools/slice_market_json.py';
  const news = '/home/manu/.openclaw/workspace/tools/slice_news_json.py';

  if (tab === 'finance') await runScript(finance);
  else if (tab === 'news') await runScript(news);
  else {
    await runScript(finance);
    await runScript(news);
  }
}

function parseCookies(req) {
  const header = req.headers.cookie || '';
  const out = {};
  header.split(';').forEach(part => {
    const idx = part.indexOf('=');
    if (idx > -1) {
      const k = part.slice(0, idx).trim();
      const v = part.slice(idx + 1).trim();
      out[k] = decodeURIComponent(v);
    }
  });
  return out;
}

function makeCookie(name, value, maxAgeSeconds = null) {
  const parts = [`${name}=${encodeURIComponent(value)}`, 'Path=/', 'HttpOnly', 'SameSite=Lax'];
  if (SESSION_SECURE) parts.push('Secure');
  if (maxAgeSeconds != null) parts.push(`Max-Age=${maxAgeSeconds}`);
  return parts.join('; ');
}

function getSession(req) {
  const cookies = parseCookies(req);
  const token = cookies[SESSION_COOKIE];
  if (!token) return null;
  const sess = sessions.get(token);
  if (!sess) return null;
  if (Date.now() > sess.expiresAt) {
    sessions.delete(token);
    return null;
  }
  return { token, ...sess };
}

function createSession(user) {
  const token = crypto.randomBytes(32).toString('hex');
  sessions.set(token, {
    user,
    createdAt: Date.now(),
    expiresAt: Date.now() + SESSION_TTL_MS
  });
  return token;
}

function clearSession(token) {
  if (token) sessions.delete(token);
}

function sendJson(res, status, body, extraHeaders = {}) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-cache',
    ...extraHeaders
  });
  res.end(JSON.stringify(body));
}

function httpsRequest({ hostname, path, method = 'GET', headers = {}, body = '' }) {
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname, path, method, headers }, resp => {
      let raw = '';
      resp.on('data', d => (raw += d));
      resp.on('end', () => resolve({ statusCode: resp.statusCode || 0, body: raw }));
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

async function verifyGoogleIdToken(idToken) {
  const path = `/tokeninfo?id_token=${encodeURIComponent(idToken)}`;
  const resp = await httpsRequest({ hostname: 'oauth2.googleapis.com', path, method: 'GET' });
  if (resp.statusCode !== 200) throw new Error('Google token verification failed');

  let payload;
  try { payload = JSON.parse(resp.body); } catch { throw new Error('Invalid token payload'); }

  if (!payload || payload.aud !== GOOGLE_CLIENT_ID) throw new Error('Invalid audience');
  if (payload.email_verified !== 'true') throw new Error('Email not verified');

  const email = (payload.email || '').toLowerCase();
  if (ALLOWED_EMAILS.size && !ALLOWED_EMAILS.has(email)) throw new Error('Email not allowed');

  return {
    sub: payload.sub,
    email,
    name: payload.name || email,
    picture: payload.picture || ''
  };
}

function buildGoogleAuthUrl(state) {
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: GOOGLE_REDIRECT_URI,
    response_type: 'code',
    scope: 'openid email profile',
    access_type: 'offline',
    include_granted_scopes: 'true',
    prompt: 'select_account',
    state
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

async function exchangeCodeForToken(code) {
  const body = querystring.stringify({
    code,
    client_id: GOOGLE_CLIENT_ID,
    client_secret: GOOGLE_CLIENT_SECRET,
    redirect_uri: GOOGLE_REDIRECT_URI,
    grant_type: 'authorization_code'
  });

  const resp = await httpsRequest({
    hostname: 'oauth2.googleapis.com',
    path: '/token',
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': Buffer.byteLength(body)
    },
    body
  });

  let payload;
  try { payload = JSON.parse(resp.body); } catch { throw new Error('Invalid token response'); }
  if (resp.statusCode !== 200 || !payload?.id_token) {
    throw new Error(payload?.error_description || payload?.error || 'OAuth token exchange failed');
  }

  return payload.id_token;
}

function requireAuth(req, res, urlObj) {
  const publicPaths = new Set([
    '/login',
    '/auth/google/start',
    '/auth/google/callback',
    '/auth/logout',
    '/auth/me',
    '/slice-logo.svg'
  ]);
  if (publicPaths.has(urlObj.pathname)) return { ok: true, session: null };

  const sess = getSession(req);
  if (sess) return { ok: true, session: sess };

  if (urlObj.pathname.startsWith('/api/') || urlObj.pathname.endsWith('.json')) {
    sendJson(res, 401, { ok: false, error: 'unauthorized' });
    return { ok: false };
  }

  res.writeHead(302, { Location: '/login' });
  res.end();
  return { ok: false };
}

setInterval(() => {
  const now = Date.now();
  for (const [state, createdAt] of oauthStates.entries()) {
    if (now - createdAt > 10 * 60 * 1000) oauthStates.delete(state);
  }
}, 60 * 1000).unref();

http.createServer(async (req, res) => {
  try {
    const urlObj = new URL(req.url, `http://${req.headers.host}`);

    if (!GOOGLE_CLIENT_ID || !GOOGLE_CLIENT_SECRET) {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('Server misconfigured: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required');
    }

    if (urlObj.pathname === '/auth/google/start') {
      const state = crypto.randomBytes(24).toString('hex');
      oauthStates.set(state, Date.now());
      res.writeHead(302, { Location: buildGoogleAuthUrl(state) });
      return res.end();
    }

    if (urlObj.pathname === '/auth/google/callback') {
      const state = urlObj.searchParams.get('state') || '';
      const code = urlObj.searchParams.get('code') || '';
      const err = urlObj.searchParams.get('error') || '';

      if (err) {
        res.writeHead(302, { Location: `/login?error=${encodeURIComponent(err)}` });
        return res.end();
      }

      if (!state || !oauthStates.has(state) || !code) {
        res.writeHead(302, { Location: '/login?error=invalid_oauth_state' });
        return res.end();
      }
      oauthStates.delete(state);

      try {
        const idToken = await exchangeCodeForToken(code);
        const user = await verifyGoogleIdToken(idToken);
        const token = createSession(user);

        res.writeHead(302, {
          'Set-Cookie': makeCookie(SESSION_COOKIE, token, Math.floor(SESSION_TTL_MS / 1000)),
          Location: '/'
        });
        return res.end();
      } catch (e) {
        res.writeHead(302, { Location: `/login?error=${encodeURIComponent(String(e.message || e))}` });
        return res.end();
      }
    }

    if (urlObj.pathname === '/auth/logout' && req.method === 'POST') {
      const sess = getSession(req);
      if (sess?.token) clearSession(sess.token);
      return sendJson(
        res,
        200,
        { ok: true },
        { 'Set-Cookie': makeCookie(SESSION_COOKIE, '', 0) }
      );
    }

    if (urlObj.pathname === '/auth/me') {
      const sess = getSession(req);
      return sendJson(res, 200, { ok: !!sess, user: sess?.user || null });
    }

    const gate = requireAuth(req, res, urlObj);
    if (!gate.ok) return;

    if (urlObj.pathname === '/api/refresh') {
      const tab = (urlObj.searchParams.get('tab') || 'all').toLowerCase();
      try {
        await refreshDataset(tab);
        return sendJson(res, 200, { ok: true, tab });
      } catch (e) {
        return sendJson(res, 500, { ok: false, error: String(e.message || e) });
      }
    }

    if (urlObj.pathname === '/login') {
      const htmlPath = path.join(ROOT, 'login.html');
      const html = fs.readFileSync(htmlPath, 'utf8');
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store'
      });
      return res.end(html);
    }

    let reqPath = urlObj.pathname;
    if (reqPath === '/') reqPath = '/index.html';
    const filePath = path.normalize(path.join(ROOT, reqPath));

    if (!filePath.startsWith(ROOT)) {
      res.writeHead(403);
      return res.end('Forbidden');
    }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404);
        return res.end('Not found');
      }
      const ext = path.extname(filePath).toLowerCase();
      res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream');
      res.setHeader('Cache-Control', ext === '.json' ? 'no-cache' : 'public, max-age=60');
      res.writeHead(200);
      res.end(data);
    });
  } catch (e) {
    res.writeHead(500);
    res.end('Server error');
  }
}).listen(PORT, '127.0.0.1', () => {
  console.log(`Slice server running at http://127.0.0.1:${PORT}`);
});
