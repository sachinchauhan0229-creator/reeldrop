# ReelDrop

Public Instagram video/Reel downloader. The default endpoint is /api/direct, a Python function using yt-dlp. No paid API and no Apify requests. /api/download only redirects to /api/direct. Photo-only posts are not supported.

## Local development
Install Python 3.10+ and Node, run `python -m pip install -r requirements.txt`, then `npm run dev`. Set PYTHON if your Python executable has a different name.

## Vercel
Framework Other; output public; no build command. The root requirements.txt installs yt-dlp for api/direct.py. No API keys required. Existing APIFY_TOKEN and DOWNLOADS_ENABLED variables are unused and can be removed.

The library is free. Vercel free hosting limits still apply; Instagram may restrict cloud IPs, require login, or change its endpoints. No guarantee of unlimited availability. No Instagram passwords, account cookies or proxy services are used. Returned media links expire. Only save content you own or have permission to save.

## Verification
Live anonymous extraction of a public Reel was successful on Vercel on 15 October 2026 before switching the frontend. Unit tests cover URL/host validation and normalization. Do not represent local or mocked tests as proof every Instagram post works.

## SEO and ownership
Canonical, sitemap and robots use https://reeldrop.jobcraft.in. Search Console verification remains pending. No indexing/ranking guarantee. Copyright notice: Sachin Chauhan, with third-party licenses preserved. yt-dlp is used under the Unlicense.

The browser downloads files through /api/save on the same site. The Python endpoint streams the attachment without buffering the entire video; the client validates the expected byte count when provided. Browser settings determine the final save location.

## Search setup
Primary host: reeldrop.jobcraft.in. reeldrop-five.vercel.app permanently redirects to it. Guides, About, Contact and sitemap are published. Search Console access was blocked by the current network filter on 16 October 2026; ownership verification, sitemap submission and indexing requests have NOT been completed. Ask the network administrator for approved access, then verify the URL-prefix property using the HTML tag and submit sitemap.xml. Never claim a guaranteed rank. No ad network or paid plan has been activated; Vercel Hobby is non-commercial.

## Custom domain and ads

GoDaddy CNAME reeldrop points to d1b5ef5b5d538525.vercel-dns-017.com. Vercel connects reeldrop.jobcraft.in to Production and provisions HTTPS. Both former Vercel hosts redirect with path preservation.

AdSense publisher ca-pub-7810129605745071 is declared for ownership and ads.txt is published. Ad loading is deliberately disabled in public/ads.js because this project is on Vercel Hobby (non-commercial use only). Move to commercial-compatible hosting or an authorized paid plan before setting ADS_ENABLED=true. Confirm AdSense approval and any applicable consent setup before enabling ads. This commit does not purchase a plan or claim ad approval. Ads are never inserted in API/media responses; the loader respects DNT/GPC. Search Console indexing and AdSense account approval are separate external steps.
