import { Innertube } from 'youtubei.js';

async function checkStream(format, player) {
  if (!format) return 'no format';
  try {
    const url = new URL(await format.decipher(player));
    if (url.protocol !== 'https:' || !url.hostname.endsWith('.googlevideo.com')) return 'invalid media host';
    const response = await fetch(url, { headers: { Range: 'bytes=0-127' }, redirect: 'error', signal: AbortSignal.timeout(4000) });
    const stream = response.body?.getReader();
    const sample = response.ok && stream ? (await stream.read()).value : null;
    await stream?.cancel();
    return { status: response.status, sampleBytes: sample?.length ?? 0 };
  } catch (error) {
    return error.name;
  }
}

export default async function handler(req, res) {
  const id = req.query.id;
  if (req.method !== 'GET' || !['WWuY4_g3Yaw', 'gPENs56vfYk'].includes(id)) return res.status(404).end();
  res.setHeader('Cache-Control', 'no-store');
  try {
    const youtube = await Innertube.create({
      fetch: (input, options) => fetch(input, { ...options, signal: AbortSignal.timeout(4500) }),
      generate_session_locally: true,
    });
    const results = await Promise.all(['WEB', 'ANDROID', 'IOS', 'TV_EMBEDDED'].map(async client => {
      try {
        const info = await youtube.getBasicInfo(id, { client });
        const formats = info.streaming_data?.adaptive_formats ?? [];
        const video = formats.find(f => f.has_video && Math.min(f.width, f.height) === 1080 && f.mime_type.startsWith('video/mp4'));
        const audio = formats.find(f => f.has_audio && f.mime_type.startsWith('audio/mp4'));
        const result = { client, status: info.playability_status?.status, reason: info.playability_status?.reason, formats: formats.length };
        if (video && audio) {
          [result.video, result.audio] = await Promise.all([checkStream(video, youtube.session.player), checkStream(audio, youtube.session.player)]);
        }
        return result;
      } catch (error) {
        return { client, error: error.message?.slice(0, 200) };
      }
    }));
    return res.json({ region: process.env.VERCEL_REGION, results });
  } catch (error) {
    return res.status(502).json({ region: process.env.VERCEL_REGION, error: error.message?.slice(0, 200) });
  }
}
