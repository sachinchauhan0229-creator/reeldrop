import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {spawn} from 'node:child_process';
const root=path.resolve(fileURLToPath(new URL('./public/',import.meta.url)));
const apiPort=Number(process.env.REELDROP_API_PORT || 3001);
const python=spawn(process.env.PYTHON || 'python',[fileURLToPath(new URL('./local-api.py',import.meta.url))],{windowsHide:true,stdio:['ignore','ignore','pipe'],env:{...process.env,REELDROP_API_PORT:String(apiPort)}});
python.stderr.on('data',data=>process.stderr.write(data));
python.on('error',()=>process.stderr.write('Python API could not start. Install requirements.txt and set PYTHON if needed.\n'));
const stop=()=>{python.kill();process.exit(0);};process.on('SIGINT',stop);process.on('SIGTERM',stop);process.on('exit',()=>python.kill());
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.json':'application/json','.webmanifest':'application/manifest+json','.xml':'application/xml','.txt':'text/plain; charset=utf-8'};
http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost');
  if(url.pathname.startsWith('/api/')){
   const proxy=http.request({hostname:'127.0.0.1',port:apiPort,path:req.url,method:req.method,headers:{...req.headers,host:req.headers.host}},upstream=>{res.writeHead(upstream.statusCode,upstream.headers);upstream.pipe(res);});
   proxy.on('error',()=>{if(!res.headersSent){res.writeHead(503,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'The local Python API is starting or unavailable. Install requirements.txt and try again.'}));}});
   req.on('aborted',()=>proxy.destroy());req.pipe(proxy);return;
  }
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end();return;}
  let relative=decodeURIComponent(url.pathname);
  if(relative.startsWith('/https://www.instagram.com/')||relative.startsWith('/https://instagram.com/')){res.writeHead(302,{Location:'/?url='+encodeURIComponent(relative.slice(1))});res.end();return;}
  if(relative==='/')relative='/index.html';
  const filename=path.resolve(root,'.'+relative);
  if(!filename.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
  const data=await readFile(filename);res.writeHead(200,{'Content-Type':mime[path.extname(filename)]||'application/octet-stream'});res.end(req.method==='HEAD'?undefined:data);
 }catch(error){res.writeHead(error.code==='ENOENT'?404:500);res.end('Page not found');}
}).listen(Number(process.env.PORT||3000),'127.0.0.1',()=>console.log('ReelDrop running at http://127.0.0.1:'+(process.env.PORT||3000)));
