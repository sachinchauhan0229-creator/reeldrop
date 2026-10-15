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
Canonical, sitemap and robots use https://reeldrop-sachin.vercel.app. Search Console verification remains pending. No indexing/ranking guarantee. Copyright notice: Sachin Chauhan, with third-party licenses preserved. yt-dlp is used under the Unlicense.
