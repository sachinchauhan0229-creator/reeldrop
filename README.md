# ReelDrop

Instagram downloader UI and Vercel Node API. Copyright notice: Sachin Chauhan.

## Local
Run `npm run dev`. No dependencies required. For local provider testing, use Node's `--env-file=.env` option with dev-server.js; never commit .env.

## Vercel
Import this repository with Framework Preset Other, no build command, output directory public. Keep the api and lib folders at repository root so Vercel deploys the function. A public-folder-only upload does NOT deploy the API.

Set APIFY_TOKEN as a sensitive server-side Vercel variable and DOWNLOADS_ENABLED=true only on the free Apify account after checking quota settings. Redeploy after changing variables. No credentials belong in public JavaScript or Git. Keep the free plan; do not enable paid overages or automatic top-ups. The free credits and pricing can change.

The API uses Apify's apify/instagram-scraper with one URL, one result, a 40-second actor timeout and a USD 0.01 per-run charge ceiling deducted from available credits. Basic per-instance throttling is not a durable global rate limiter. Add Vercel Firewall rules or durable shared limits as traffic grows; the provider's free account quota is the hard allowance cap. If retrieval takes too long or a post is unavailable, the UI shows an error. Returned CDN links expire and saving behavior depends on the browser.

## SEO
Canonical, Open Graph metadata, robots.txt, sitemap.xml and WebSite structured data use https://reeldrop-sachin.vercel.app. Update all URLs when adding a custom domain. Verify the URL prefix in Google Search Console and submit sitemap.xml after actual downloads work. No indexing or ranking is guaranteed.

## Checks
`npm run check` and `npm test`. Tests mock provider responses. Live provider authentication, real Reel/photo/carousel downloads and quota failure checks remain pending until account setup.

Docs: https://apify.com/apify/instagram-scraper/input-schema and https://docs.apify.com/api/v2/actor-run-sync-get-dataset-items-post
