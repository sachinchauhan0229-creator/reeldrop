(()=>{'use strict';const $=id=>document.getElementById(id),fmt=v=>Number(v||0).toLocaleString('en-IN');let busy=false;
const endpoint='https://jobcraft.in/api/reeldrop-analytics/';
function request(op,query={},options={}){
  return fetch(endpoint+'?'+new URLSearchParams({op,...query}),{
    cache:'no-store',credentials:'include',...options
  });
}

const actionLabels={"page_view":"Page viewed","search_started":"Media search started","search_results":"Search results found","search_failed":"Search failed","video_download":"Video download","photo_download":"Photo download","zip_download":"ZIP download","download_failed":"Download failed"};
let activityPage=0,activityRequest;
const requestActivity=(query,signal)=>request('activity',Object.fromEntries(query),{signal});
const formatTime=value=>new Date(value).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'});
async function loadActivity(page=0){
  const visitor=$('activity-browser').value.trim().toLowerCase();
  if(visitor&&!/^[a-f0-9]{12}$/.test(visitor)){
    $('activity-status').textContent='Enter a 12-character browser ID.';
    return;
  }
  activityRequest?.abort();
  const request=new AbortController();
  activityRequest=request;
  $('activity-status').textContent='Loading activity…';
  $('activity-prev').disabled=true;
  $('activity-next').disabled=true;
  try{
    const query=new URLSearchParams({days:$('period').value,visitor,action:$('activity-action').value,page});
    const res=await requestActivity(query,request.signal);
    if(request.signal.aborted)return;
    if(res.status===401){signedIn(false);return;}
    const data=await res.json();
    if(request.signal.aborted)return;
    if(!res.ok)throw Error(data.error);
    activityPage=page;
    for(const id of ['downloads','downloaders','searches'])$(id).textContent=fmt(data.counts[id]);
    $('action-breakdown').replaceChildren();
    for(const item of data.breakdown){
      const li=document.createElement('li');
      li.textContent=(actionLabels[item.action]||item.action)+' — '+fmt(item.total);
      $('action-breakdown').append(li);
    }
    if(!data.breakdown.length){
      const li=document.createElement('li');li.textContent='No actions recorded in this period.';
      $('action-breakdown').append(li);
    }
    $('activity-rows').replaceChildren();
    for(const item of data.events){
      const row=document.createElement('tr');
      cell(row,formatTime(item.at));
      const browser=document.createElement('button');
      browser.type='button';browser.className='activity-browser-link';browser.textContent=item.visitor;
      browser.title='Show activity for this browser';
      browser.onclick=()=>{$('activity-browser').value=item.visitor;loadActivity();};
      const browserCell=document.createElement('td');browserCell.append(browser);row.append(browserCell);
      cell(row,item.session);cell(row,actionLabels[item.action]||item.action);cell(row,item.path);
      $('activity-rows').append(row);
    }
    $('activity-status').textContent=data.events.length
      ? 'Page '+(page+1)+' · '+data.events.length+' events'
      : 'No activity matches these filters.';
    $('activity-prev').disabled=page===0;
    $('activity-next').disabled=!data.hasMore;
  }catch(error){
    if(!request.signal.aborted)$('activity-status').textContent=error.message||'Could not load activity.';
  }
}
$('activity-apply').onclick=()=>loadActivity();
$('activity-clear').onclick=()=>{$('activity-browser').value='';$('activity-action').value='all';loadActivity();};
$('activity-prev').onclick=()=>loadActivity(Math.max(0,activityPage-1));
$('activity-next').onclick=()=>loadActivity(activityPage+1);
function signedIn(value){if(!value){activityRequest?.abort();$('activity-rows').replaceChildren();}$('login').hidden=value;$('report').hidden=!value;$('logout').hidden=!value}function cell(row,value){const td=document.createElement('td');td.textContent=value;row.append(td)}async function report(){if(busy)return;busy=true;$('refresh').disabled=true;try{const res=await request('stats',{days:$('period').value});if(res.status===401){signedIn(false);return}const data=await res.json();if(!res.ok)throw Error(data.error);signedIn(true);void loadActivity();for(const id of ['visitors','sessions','views','today_visitors','today_views'])$(id).textContent=fmt(data.totals[id]);$('status').textContent='Updated '+new Date(data.updated).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST';$('daily').replaceChildren();$('pages').replaceChildren();for(const item of data.daily){const row=document.createElement('tr');cell(row,item.day);cell(row,fmt(item.visitors));cell(row,fmt(item.sessions));cell(row,fmt(item.views));$('daily').append(row)}for(const item of data.pages){const row=document.createElement('tr');cell(row,item.path);cell(row,fmt(item.visitors));cell(row,fmt(item.views));$('pages').append(row)}for(const id of ['daily','pages'])if(!$(id).children.length){const row=document.createElement('tr');const td=document.createElement('td');td.colSpan=id==='daily'?4:3;td.textContent='No visits recorded in this period.';row.append(td);$(id).append(row)}$('chart').replaceChildren();const byDay=new Map(data.daily.map(d=>[d.day,d.visitors]));const today=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'}));const max=Math.max(1,...data.daily.map(d=>d.visitors));for(let i=data.days-1;i>=0;i--){const d=new Date(today);d.setDate(d.getDate()-i);const day=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`,count=byDay.get(day)||0,bar=document.createElement('div');bar.className='bar';bar.style.height=Math.max(2,count/max*110)+'px';bar.title=day+': '+fmt(count)+' unique browsers';bar.setAttribute('role','img');bar.setAttribute('aria-label',bar.title);$('chart').append(bar)}$('started').textContent=data.totals.started?'First recorded visit: '+new Date(data.totals.started).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST. All-time totals stay saved across deployments.':'Counting is active. Your first visit will appear here.'}catch(e){($('report').hidden?$('login-error'):$('status')).textContent=e.message||'Could not load report. Please retry.'}finally{busy=false;$('refresh').disabled=false}}$('login-form').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;$('login-error').textContent='';try{const res=await request('login',{},{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('username').value,password:$('password').value})});const data=await res.json();if(!res.ok)throw Error(data.error);$('password').value='';await report()}catch(err){$('login-error').textContent=err.message||'Unable to sign in'}finally{button.disabled=false}};$('logout').onclick=async()=>{await request('logout',{},{method:'POST'});signedIn(false)};$('refresh').onclick=report;$('period').onchange=report;report()})();
