const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');

const ROOT = path.join(__dirname, 'web');
const PORT = process.env.PORT || 8787;

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

http.createServer(async (req, res) => {
  try {
    const urlObj = new URL(req.url, `http://${req.headers.host}`);

    if (urlObj.pathname === '/api/refresh') {
      const tab = (urlObj.searchParams.get('tab') || 'all').toLowerCase();
      try {
        await refreshDataset(tab);
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-cache' });
        return res.end(JSON.stringify({ ok: true, tab }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        return res.end(JSON.stringify({ ok: false, error: String(e.message || e) }));
      }
    }

    let reqPath = urlObj.pathname;
    if (reqPath === '/') reqPath = '/index.html';
    const filePath = path.normalize(path.join(ROOT, reqPath));

    if (!filePath.startsWith(ROOT)) {
      res.writeHead(403); return res.end('Forbidden');
    }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404); return res.end('Not found');
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
