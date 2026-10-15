const form = document.querySelector('#download-form');
const input = document.querySelector('#url');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const submit = document.querySelector('#submit');
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
      const target = new URL(item.url); if(target.protocol !== 'https:') continue;
      const link = document.createElement('a'); link.href = target.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.className = 'media-link'; link.textContent = `Open ${item.type === 'image' ? 'photo' : 'media'} ${index + 1} ↗`; results.append(link);
    }
    status.textContent = results.children.length ? 'Your media links are ready. Open a link to save the file.' : 'No downloadable media found.';
  } catch(error) { status.textContent = error.name === 'TimeoutError' ? 'This request took too long. Please try again.' : error.message; }
  finally { submit.disabled = false; }
});
