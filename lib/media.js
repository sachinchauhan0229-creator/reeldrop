export function normalizeInstagramUrl(value) {
  if(typeof value !== 'string' || value.length > 2048) return null;
  try {
    const url = new URL(value.trim());
    if(url.protocol !== 'https:' || url.username || url.password || url.port || !['instagram.com','www.instagram.com','m.instagram.com'].includes(url.hostname)) return null;
    const match = /^\/(p|reel|reels|tv)\/([A-Za-z0-9_-]{5,64})\/?$/.exec(url.pathname);
    if(!match) return null;
    return `https://www.instagram.com/${match[1] === 'reels' ? 'reel' : match[1]}/${match[2]}/`;
  } catch {return null;}
}
function safeMedia(value) {
  try {
    const url = new URL(value);
    if(url.protocol !== 'https:' || url.username || url.password || url.port) return null;
    if(!['cdninstagram.com','fbcdn.net'].some(domain => url.hostname === domain || url.hostname.endsWith('.'+domain))) return null;
    return url.href;
  } catch {return null;}
}
export function extractMedia(items) {
  if(!Array.isArray(items)) return [];
  const media = [],seen = new Set();
  function add(item) {
    if(!item || typeof item !== 'object') return;
    if(Array.isArray(item.childPosts) && item.childPosts.length) {item.childPosts.slice(0,20).forEach(add);return;}
    const isVideo = item.type === 'Video' || Boolean(item.videoUrl);
    const url = safeMedia(isVideo ? item.videoUrl : item.displayUrl);
    if(url && !seen.has(url)) {seen.add(url);media.push({url,type:isVideo?'video':'image'});}
  }
  items.slice(0,1).forEach(add);
  return media;
}
