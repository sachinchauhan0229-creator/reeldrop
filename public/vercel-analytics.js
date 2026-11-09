// Vercel Web Analytics integration
// This script initializes Vercel Web Analytics for the site
import { inject } from './vendor/vercel-analytics.mjs';

// Initialize analytics in production mode
inject({
  mode: 'production',
  debug: false
});
