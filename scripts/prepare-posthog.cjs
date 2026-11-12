const fs = require('node:fs');
const path = require('node:path');

module.exports = function preparePostHog(output) {
  const token = process.env.POSTHOG_PROJECT_TOKEN || '';
  const host = process.env.POSTHOG_HOST || '';
  if ((token || host) && (!/^phc_[A-Za-z0-9_-]+$/.test(token) ||
      !/^https:\/\/[a-z-]+\.i\.posthog\.com$/.test(host))) {
    throw Error('Set POSTHOG_PROJECT_TOKEN and POSTHOG_HOST before building.');
  }
  const sdk = path.dirname(require.resolve('posthog-js/package.json'));
  fs.mkdirSync(path.join(output, 'vendor'), {recursive: true});
  fs.copyFileSync(path.join(sdk, 'dist/module.no-external.js'), path.join(output, 'vendor/posthog.mjs'));
  fs.writeFileSync(path.join(output, 'posthog-config.json'), JSON.stringify({token, host}));
};
