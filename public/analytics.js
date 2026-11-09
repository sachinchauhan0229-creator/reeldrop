(()=>{
  const endpoint='https://jobcraft.in/api/reeldrop-analytics?op=event';
  function track(action){
    try{
      if(location.hostname!=='reeldrop.jobcraft.in'||/^\/(admin|api)([/.]|$)/i.test(location.pathname)||
          navigator.doNotTrack==='1'||navigator.globalPrivacyControl===true||!crypto.randomUUID)return;
      let visitor=localStorage.getItem('rd-analytics-visitor');
      if(!visitor){visitor=crypto.randomUUID();localStorage.setItem('rd-analytics-visitor',visitor);}
      const now=Date.now();
      let session;
      try{session=JSON.parse(localStorage.getItem('rd-analytics-session'));}catch{}
      if(!session?.id||!Number.isFinite(session.at)||now-session.at>1800000)session={id:crypto.randomUUID()};
      session.at=now;
      localStorage.setItem('rd-analytics-session',JSON.stringify(session));
      // Plain text keeps the public request simple while the API still checks its origin.
      fetch(endpoint,{method:'POST',credentials:'omit',keepalive:true,
        body:JSON.stringify({id:crypto.randomUUID(),visitor,session:session.id,path:location.pathname,action})
      }).catch(()=>{});
    }catch{}
  }
  window.reelDropTrack=track;
  track('page_view');
})();
