import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import download from './api/download.js';

const root = path.resolve(fileURLToPath(new URL('./public/', import.meta.url)));
const types = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'};
const server = http.createServer(async (req,res) => {
  try {
    const url = new URL(req.url,'http://localhost');
    if(url.pathname === '/api/download') {
      let body = '';
      for await (const chunk of req) {
        body += chunk;
        if(Buffer.byteLength(body) > 8192) {res.writeHead(413);res.end('Request too large');return;}
      }
      try { req.body = body ? JSON.parse(body) : {}; }
      catch {res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'Invalid JSON.'}));return;}
      res.status = code => {res.statusCode = code;return res;};
      res.json = data => {res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
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
