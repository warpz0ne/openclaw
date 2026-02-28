const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const crypto = require('crypto');
const https = require('https');

const ROOT = path.join(__dirname, 'web');
const PORT = process.env.PORT || 8787;
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID || '';
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

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', chunk => {
      data += chunk;
      if (data.length > 1_000_000) {
        reject(new Error('Body too large'));
        req.destroy();
      }
    });
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch {
        reject(new Error('Invalid JSON'));
      }
    });
    req.on('error', reject);
  });
}

function verifyGoogleIdToken(idToken) {
  const url = `https://oauth2.googleapis.com/tokeninfo?id_token=${encodeURIComponent(idToken)}`;
  return new Promise((resolve, reject) => {
    https.get(url, resp => {
      let raw = '';
      resp.on('data', d => (raw += d));
      resp.on('end', () => {
        if (resp.statusCode !== 200) return reject(new Error('Google token verification failed'));
        try {
          const payload = JSON.parse(raw);
          if (!payload || payload.aud !== GOOGLE_CLIENT_ID) return reject(new Error('Invalid audience'));
          if (payload.email_verified !== 'true') return reject(new Error('Email not verified'));
          const email = (payload.email || '').toLowerCase();
          if (ALLOWED_EMAILS.size && !ALLOWED_EMAILS.has(email)) return reject(new Error('Email not allowed'));
          resolve({
            sub: payload.sub,
            email,
            name: payload.name || email,
            picture: payload.picture || ''
          });
        } catch {
          reject(new Error('Invalid token payload'));
        }
      });
    }).on('error', reject);
  });
}

function sendJson(res, status, body, extraHeaders = {}) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-cache',
    ...extraHeaders
  });
  res.end(JSON.stringify(body));
}

function requireAuth(req, res, urlObj) {
  const publicPaths = new Set(['/login', '/auth/google', '/auth/logout', '/auth/me', '/slice-logo.svg']);
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

http
  .createServer(async (req, res) => {
    try {
      const urlObj = new URL(req.url, `http://${req.headers.host}`);

      if (!GOOGLE_CLIENT_ID) {
        res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
        return res.end('Server misconfigured: GOOGLE_CLIENT_ID is required');
      }

      if (urlObj.pathname === '/auth/google' && req.method === 'POST') {
        try {
          const body = await readJsonBody(req);
          if (!body.credential) return sendJson(res, 400, { ok: false, error: 'Missing credential' });
          const user = await verifyGoogleIdToken(body.credential);
          const token = createSession(user);
          return sendJson(
            res,
            200,
            { ok: true, user },
            { 'Set-Cookie': makeCookie(SESSION_COOKIE, token, Math.floor(SESSION_TTL_MS / 1000)) }
          );
        } catch (e) {
          return sendJson(res, 401, { ok: false, error: String(e.message || e) });
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
        const html = fs.readFileSync(htmlPath, 'utf8').replaceAll('__GOOGLE_CLIENT_ID__', GOOGLE_CLIENT_ID);
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
  })
  .listen(PORT, '127.0.0.1', () => {
    console.log(`Slice server running at http://127.0.0.1:${PORT}`);
  });
