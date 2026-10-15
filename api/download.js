import {normalizeInstagramUrl, extractMedia} from '../lib/media.js';
// Best-effort per-instance throttling; provider free-plan quotas remain the hard cap.
const requests = new Map();
let active = 0;
export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if(req.method !== 'POST') { res.setHeader('Allow','POST'); return res.status(405).json({error:'Use POST.'}); }
  let body = req.body;
  if(typeof body === 'string') {try {body = JSON.parse(body);} catch {return res.status(400).json({error:'Invalid request.'});}}
  const url = normalizeInstagramUrl(body?.url);
  if(!url) return res.status(400).json({error:'Use a public Instagram post or Reel link.'});
  if(!process.env.APIFY_TOKEN || process.env.DOWNLOADS_ENABLED !== 'true') return res.status(503).json({error:'Downloads are not available yet. Please check back after the media service is connected.'});
  if(req.headers.origin && req.headers.host && req.headers.origin !== `https://${req.headers.host}` && req.headers.origin !== `http://${req.headers.host}`) return res.status(403).json({error:'Use the ReelDrop website to request downloads.'});
  const key = String(req.headers['x-forwarded-for'] || req.socket?.remoteAddress || 'unknown').split(',')[0].trim();
  const now = Date.now();
  for(const [ip, item] of requests) if(item.reset <= now) requests.delete(ip);
  if(requests.size > 5000 || active >= 2) return res.status(429).json({error:'The service is busy. Please try again shortly.'});
  const count = requests.get(key) || {used:0,reset:now+60000};
  if(count.used >= 3) {res.setHeader('Retry-After','60');return res.status(429).json({error:'Please wait a minute before requesting more links.'});}
  count.used++; requests.set(key,count); active++;
  try {
    const endpoint = new URL('https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items');
    endpoint.search = new URLSearchParams({timeout:'40',maxTotalChargeUsd:'0.01',limit:'1',clean:'true'}).toString();
    const upstream = await fetch(endpoint,{method:'POST',headers:{Authorization:`Bearer ${process.env.APIFY_TOKEN}`,'Content-Type':'application/json'},body:JSON.stringify({directUrls:[url],resultsType:url.includes('/reel/')?'reels':'posts',resultsLimit:1,addParentData:false}),signal:AbortSignal.timeout(45000)});
    if(!upstream.ok) {
      const error = [401,403].includes(upstream.status) ? 'The media service needs attention. Please try later.' : [402,429].includes(upstream.status) ? 'The free download allowance is currently unavailable. Please try later.' : 'Could not retrieve this post. Try again later.';
      return res.status(502).json({error});
    }
    const media = extractMedia(await upstream.json());
    if(!media.length) return res.status(404).json({error:'No downloadable media found. Check that this post is public and still available.'});
    return res.status(200).json({media});
  } catch(error) {return res.status(502).json({error:['TimeoutError','AbortError'].includes(error.name) ? 'The media service took too long. Please try again later.' : 'The media service is temporarily unavailable.'});}
  finally {active--;}
}
