'use strict';

const fs = require('fs/promises');
const http = require('http');
const path = require('path');

const port = Number(process.env.PORT || '8080');
const staffDataPath = process.env.STAFF_DATA_PATH;
const cacheDir = process.env.CACHE_DIR || '/tmp/people-directory';

let ready = false;
let staff = [];

async function bootstrap() {
  if (!staffDataPath) {
    throw new Error('STAFF_DATA_PATH is required');
  }
  await fs.mkdir(cacheDir, { recursive: true });
  staff = JSON.parse(await fs.readFile(staffDataPath, 'utf8'));
  await fs.writeFile(path.join(cacheDir, 'ready'), `${staff.length}\n`, 'utf8');
  ready = true;
  console.log(JSON.stringify({ event: 'directory_loaded', records: staff.length }));
}

const server = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json');
  if (req.url === '/livez') {
    res.writeHead(200).end(JSON.stringify({ status: 'alive' }));
    return;
  }
  if (req.url === '/readyz') {
    res.writeHead(ready ? 200 : 503).end(JSON.stringify({ status: ready ? 'ready' : 'loading' }));
    return;
  }
  if (req.url === '/api/staff') {
    res.writeHead(ready ? 200 : 503).end(JSON.stringify(ready ? staff : { error: 'not ready' }));
    return;
  }
  res.writeHead(404).end(JSON.stringify({ error: 'not found' }));
});

server.listen(port, '0.0.0.0', () => {
  console.log(JSON.stringify({ event: 'listening', port }));
  bootstrap().catch((error) => console.error(JSON.stringify({ event: 'bootstrap_failed', message: error.message })));
});

process.on('SIGTERM', () => {
  ready = false;
  server.close(() => process.exit(0));
});
