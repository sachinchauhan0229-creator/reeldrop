const site = location.hostname === 'jobcraft.in' ? 'jobcraft'
  : location.hostname === 'reeldrop.jobcraft.in' ? 'reeldrop' : '';
const excluded = /^\/(admin|api|dashboard)([/.]|$)/i;
const optedOut = () => navigator.doNotTrack === '1' || navigator.globalPrivacyControl === true;
const allowed = new Set(['$pageview', 'search_started', 'search_results', 'search_failed',
  'video_download', 'photo_download', 'zip_download', 'download_failed',
  'resume_download', 'letter_download', 'resume_backup_download', 'letter_backup_download',
  'resume_print', 'letter_print', 'resume_save', 'letter_save', 'resume_import', 'letter_import',
  'resume_open', 'letter_open', 'files_open', 'template_select', 'sample_use', 'resume_review',
  'resume_new', 'letter_new', 'resume_duplicate', 'letter_duplicate', 'resume_delete', 'letter_delete']);

if (site && !excluded.test(location.pathname) && !optedOut()) {
  const queue = [];
  let sdk;
  const capture = action => {
    if (!allowed.has(action) || optedOut() || excluded.test(location.pathname)) return;
    if (sdk) sdk.capture(action, {site});
    else if (queue.length < 50) queue.push(action);
  };
  const previous = site === 'jobcraft' ? window.jobcraftTrack : window.reelDropTrack;
  const track = action => {
    previous?.(action);
    if (action) capture(action);
  };
  if (site === 'jobcraft') {
    window.jobcraftTrack = track;
    window.trackJobCraft = track;
  } else {
    window.reelDropTrack = track;
  }

  try {
    const response = await fetch('/api/posthog-config', {cache: 'no-store'});
    if (!response.ok) throw Error('PostHog configuration unavailable');
    const config = await response.json();
    if (!/^phc_[A-Za-z0-9_-]+$/.test(config.token || '') ||
        !/^https:\/\/[a-z-]+\.i\.posthog\.com$/.test(config.host || '') || optedOut()) {
      throw Error('PostHog is not configured');
    }
    const {default: posthog} = await import('/vendor/posthog.mjs');
    posthog.init(config.token, {
      api_host: config.host,
      defaults: '2026-08-30',
      person_profiles: 'never',
      persistence: 'localStorage',
      persistence_name: 'ph_' + site,
      cross_subdomain_cookie: false,
      autocapture: false,
      capture_pageview: false,
      capture_pageleave: false,
      capture_dead_clicks: false,
      capture_exceptions: false,
      capture_heatmaps: false,
      capture_performance: false,
      disable_session_recording: true,
      disable_surveys: true,
      advanced_disable_feature_flags: true,
      before_send(event) {
        if (!allowed.has(event.event) || optedOut() || excluded.test(location.pathname)) return null;
        const source = event.properties || {};
        const properties = {site, $current_url: location.origin + location.pathname,
          $host: location.hostname, $pathname: location.pathname, $process_person_profile: false};
        for (const key of ['token', 'distinct_id', '$device_id', '$session_id', '$window_id',
          '$lib', '$lib_version', '$browser', '$browser_version', '$os', '$os_version',
          '$device_type', '$screen_width', '$screen_height', '$viewport_width', '$viewport_height']) {
          if (typeof source[key] === 'string' || typeof source[key] === 'number') properties[key] = source[key];
        }
        try { properties.$referrer = document.referrer ? new URL(document.referrer).origin : ''; }
        catch { properties.$referrer = ''; }
        return {...event, properties};
      },
    });
    sdk = posthog;
    capture('$pageview');
    for (const action of queue) capture(action);
    queue.length = 0;
  } catch {
    // Existing website analytics and document/download controls work independently.
  }
}
