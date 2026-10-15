import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import download from './api/download.js';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {normalizeInstagramUrl} from './lib/media.js';
const runPython = promisify(execFile);

const root = path.resolve(fileURLToPath(new URL('./public/', import.meta.url)));
const types = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'};
const server = http.createServer(async (req,res) => {
  try {
    const url = new URL(req.url,'http://localhost');
    if(['/api/download','/api/direct'].includes(url.pathname)) {
      let body = '';
      for await (const chunk of req) {
        body += chunk;
        if(Buffer.byteLength(body) > 8192) {res.writeHead(413);res.end('Request too large');return;}
      }
      try { req.body = body ? JSON.parse(body) : {}; }
      catch {res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'Invalid JSON.'}));return;}
      res.status = code => {res.statusCode = code;return res;};
      res.json = data => {res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
      if(url.pathname === '/api/direct') {
        if(req.method !== 'POST') return res.status(405).json({error:'Use POST.'});
        const link = normalizeInstagramUrl(req.body?.url);
        if(!link) return res.status(400).json({error:'Use a public Instagram video link.'});
        try {
          const {stdout} = await runPython(process.env.PYTHON || 'python',[fileURLToPath(new URL('./api/direct.py',import.meta.url)),link],{timeout:50000,maxBuffer:1048576});
          const result = JSON.parse(stdout);
          return res.status(result.media?.length ? 200 : 502).json(result.error ? result : result.media?.length ? result : {error:'No public video could be retrieved.'});
        } catch {return res.status(502).json({error:'The local Python downloader is unavailable. Install requirements.txt and try again.'});}
      }
      return download(req,res);
    }
    if(!['GET','HEAD'].includes(req.method)) {res.writeHead(405);res.end();return;}
    const filename = path.resolve(root,'.' + decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname));
    if(!filename.startsWith(root + path.sep) && filename !== path.join(root,'index.html')) {res.writeHead(403);res.end();return;}
    const data = await readFile(filename);
    res.writeHead(200,{'Content-Type':types[path.extname(filename)] || 'application/octet-stream'});
    res.end(req.method === 'HEAD' ? undefined : data);
  } catch(error) {res.writeHead(error.code === 'ENOENT' ? 404 : 500);res.end('Unable to serve this request.');}
});
const port = Number(process.env.PORT || 3000);
server.listen(port,'127.0.0.1',()=>console.log(`ReelDrop running at http://127.0.0.1:${port}`));
