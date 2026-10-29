# ReelDrop

Public Instagram media downloader on https://reeldrop.jobcraft.in. Copyright notice: Sachin Chauhan. Existing domain redirects and disabled AdSense configuration are retained.

## Features
- Public photo/video/Reel/legacy IGTV URLs, ordered mixed carousels and source-provided quality variants.
- Same-page previews and downloads through a strict Instagram CDN proxy; no external media tab.
- Caption and author display; individual downloads or browser ZIP for selected items (60 MB total ZIP limit).
- Paste/Clear controls, cancellation, byte progress and basic per-instance request throttling.
- Story/Highlight and public-profile lookup attempts with explicit access errors when Instagram requires login. No private-account access or passwords.
- 25 interface-control language choices; help content in English and Hindi. This does not claim fully translated articles in 25 languages.
- REST API docs at /api.html; stateless MCP tools at /api/mcp documented at /mcp.html.
- Installable PWA with Android/iOS instructions; no signed APK is distributed.
- Address-bar query shortcut /?url=INSTAGRAM_LINK, plus a safe Instagram-prefixed URL fallback.

## Local setup
Python 3.10+ and Node are needed. Run python -m pip install -r requirements.txt, npm ci, then npm run dev. Set PYTHON if your Python executable has another name. Node serves static files and starts a local Python API process on port 3001. Set REELDROP_API_PORT to change it. No paid media API or secret is needed.

## Checks
npm run check; npm test; npm run test:python. Python unit tests mock network responses; live checks must be reported separately. For a production smoke check, use a public photo, Reel and mixed carousel that you have permission to download. Check MIME type, byte count and ZIP item types.

## Vercel
Framework Other, output public, no build command. requirements.txt includes yt-dlp with its curl-cffi optional networking dependency. Do not remove the custom domain, redirects, ads.txt or disabled ads.js. Current code never calls Apify; old APIFY_TOKEN/DOWNLOADS_ENABLED settings are unused. AdSense loading stays disabled until commercial-compatible hosting, approval and consent setup are authorized.

## Limits and honest feature scope
Instagram can restrict even public content and cloud IPs. Story/Profile availability is conditional and is not guaranteed anonymous access. No account search, follower lists, liker lists, comment scraping, or OAuth account integration is implemented. FastDL's separate paid MCP/API product advertises additional account-data features; those are not represented as working here. No paid plan, proxy subscription, APK-signing account or media-provider key is created. Hosting resource allowances still apply. The API uses bounded 90-second public metadata caching; it does not persist a browsing history or media database.

## Research references
FastDL main tool: https://fastdl.app/en5IW
FastDL Story/Viewer/API/MCP/Android pages were inspected on 29 October 2026. Source claims such as unlimited downloads, guaranteed anonymity and available quality were not copied as product guarantees. ReelDrop keeps its own branding, text and source code.
Extractor docs: https://github.com/yt-dlp/yt-dlp
MCP protocol: https://modelcontextprotocol.io/specification/2025-06-18

## SEO
Canonical and sitemap URLs retain reeldrop.jobcraft.in. Search Console ownership/indexing status is external and is not inferred by this feature update. No ranking or AdSense approval is guaranteed.
