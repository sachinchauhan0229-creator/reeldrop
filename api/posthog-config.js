export default function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'GET') return res.status(405).end();
  res.status(200).json({token: process.env.POSTHOG_PROJECT_TOKEN || '', host: process.env.POSTHOG_HOST || ''});
}
