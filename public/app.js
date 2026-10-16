const form = document.querySelector('#download-form');
const input = document.querySelector('#url');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const submit = document.querySelector('#submit');
async function saveVideo(postUrl, index, button) {
  button.disabled = true;
  const previousLabel = button.textContent;
  button.textContent = 'Downloading…';
  status.textContent = 'Downloading your video. Keep this page open…';
  try {
    const endpoint = '/api/save?' + new URLSearchParams({url:postUrl,index:String(index)});
    const response = await fetch(endpoint,{signal:AbortSignal.timeout(65000)});
    if(!response.ok || !response.headers.get('content-type')?.startsWith('video/')) {
      const error = await response.json().catch(()=>({}));
      throw new Error(error.error || 'The video could not be downloaded. Please try again.');
    }
    const blob = await response.blob();
    if(!blob.size) throw new Error('The video was empty. Please try again.');
    const expectedSize = Number(response.headers.get('x-media-size'));
    if(expectedSize > 0 && blob.size !== expectedSize) throw new Error('The video download was interrupted. Please try again.');
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl; anchor.download = `ReelDrop-${new URL(postUrl).pathname.split('/').filter(Boolean).pop()}-${index+1}.mp4`;
    document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(()=>URL.revokeObjectURL(objectUrl),60000);
    status.textContent = 'Download started. Check your browser’s Downloads folder.';
  } catch(error) {
    status.textContent = error.name === 'TimeoutError' ? 'The download took too long. Please try again.' : error.message;
  } finally {button.disabled=false;button.textContent=previousLabel;}
}
document.querySelector('#paste').addEventListener('click', async () => {
  try { input.value = await navigator.clipboard.readText(); input.focus(); }
  catch { status.textContent = 'Use your browser’s Paste option in the link field.'; input.focus(); }
});
form.addEventListener('submit', async event => {
  event.preventDefault(); results.replaceChildren();
  let url;
  try { url = new URL(input.value.trim()); } catch { status.textContent = 'Enter a valid Instagram link.'; return; }
  if (url.protocol !== 'https:' || !['instagram.com','www.instagram.com','m.instagram.com'].includes(url.hostname) || !/^\/(p|reel|reels|tv)\/[^/]+/.test(url.pathname)) {
    status.textContent = 'Paste a public Instagram post or Reel link.'; return;
  }
  submit.disabled = true; status.textContent = 'Finding available media…';
  try {
    const response = await fetch('/api/direct', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url:url.href}), signal:AbortSignal.timeout(55000)});
    if(!response.headers.get('content-type')?.includes('application/json')) throw new Error('Downloads are not available yet. Please try again after the media service is connected.');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Unable to fetch this post. Please try again.');
    if(!Array.isArray(data.media)) throw new Error('No downloadable media found.');
    for (const [index, item] of data.media.entries()) {
      if(item.type !== 'video') continue;
      const button = document.createElement('button'); button.type='button'; button.className='media-link download-video'; button.textContent = data.media.length === 1 ? 'Download video ↓' : `Download video ${index+1} ↓`;
      button.addEventListener('click',()=>saveVideo(url.href,index,button)); results.append(button);
    }
    status.textContent = results.children.length ? 'Your video is ready to download.' : 'No downloadable video found.';
    if(results.children.length === 1) await saveVideo(url.href,0,results.children[0]);
  } catch(error) { status.textContent = error.name === 'TimeoutError' ? 'This request took too long. Please try again.' : error.message; }
  finally { submit.disabled = false; }
});

