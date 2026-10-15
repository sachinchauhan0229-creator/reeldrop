// Compatibility redirect. All extraction runs locally through yt-dlp; no media API is called.
export default function handler(req,res) {
 res.setHeader('Cache-Control','no-store');
 if(req.method!=='POST'){res.setHeader('Allow','POST');return res.status(405).json({error:'Use POST.'});}
 res.setHeader('Location','/api/direct');res.status(307).end();
}
