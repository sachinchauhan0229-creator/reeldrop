// Enable only after commercial-compatible hosting, AdSense approval and consent setup.
const ADS_ENABLED = false;
if (ADS_ENABLED && navigator.doNotTrack !== '1' && window.doNotTrack !== '1' && !navigator.globalPrivacyControl) {
  const script = document.createElement('script');
  script.async = true;
  script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7810129605745071';
  script.crossOrigin = 'anonymous';
  document.head.appendChild(script);
}
