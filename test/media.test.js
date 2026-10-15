import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalizeInstagramUrl,extractMedia} from '../lib/media.js';
import handler from '../api/download.js';
test('normalizes public URLs and strips tracking',()=>{
 assert.equal(normalizeInstagramUrl('https://instagram.com/reels/Abcd_123/?igsh=abc'),'https://www.instagram.com/reel/Abcd_123/');
 for(const value of ['https://instagram.com.evil.test/p/ABCDE/','https://user:pass@instagram.com/p/ABCDE/','http://instagram.com/p/ABCDE/','https://instagram.com/profile/','https://instagram.com:444/p/ABCDE/','https://instagram.com/p/ABCDE/extra',null]) assert.equal(normalizeInstagramUrl(value),null);
});
test('extracts video and mixed carousel without returning video thumbnails',()=>{
 const video = {type:'Video',videoUrl:'https://scontent.cdninstagram.com/clip.mp4',displayUrl:'https://scontent.cdninstagram.com/thumb.jpg'};
 assert.deepEqual(extractMedia([video]),[{url:video.videoUrl,type:'video'}]);
 assert.equal(extractMedia([{childPosts:[video,{displayUrl:'https://a.fbcdn.net/photo.jpg'},video]}]).length,2);
 assert.deepEqual(extractMedia([{videoUrl:'https://evil.test/file.mp4'}]),[]);
 assert.deepEqual(extractMedia([{type:'Video',displayUrl:video.displayUrl}]),[]);
});
function response(){return {headers:{},setHeader(k,v){this.headers[k]=v;},status(code){this.code=code;return this;},json(body){this.body=body;return this;}};}
test('API rejects bad links and stays closed without setup', async()=>{
 const previous = process.env.DOWNLOADS_ENABLED; delete process.env.DOWNLOADS_ENABLED;
 try {
  const invalid=response(); await handler({method:'POST',body:{url:'https://evil.test'},headers:{}},invalid);assert.equal(invalid.code,400);
  const missing=response();await handler({method:'POST',body:{url:'https://instagram.com/p/ABCDE/'},headers:{}},missing);assert.equal(missing.code,503);
 } finally {if(previous!==undefined)process.env.DOWNLOADS_ENABLED=previous;}
});
test('API calls the provider with a capped single-post request and normalizes output',async()=>{
 const oldFetch=globalThis.fetch, oldToken=process.env.APIFY_TOKEN, oldEnabled=process.env.DOWNLOADS_ENABLED;
 process.env.APIFY_TOKEN='test-only';process.env.DOWNLOADS_ENABLED='true';
 globalThis.fetch=async (url,options)=>{assert.equal(url.searchParams.get('maxTotalChargeUsd'),'0.01');assert.equal(JSON.parse(options.body).resultsLimit,1);assert.equal(options.headers.Authorization,'Bearer test-only');return {ok:true,json:async()=>[{videoUrl:'https://scontent.cdninstagram.com/video.mp4'}]};};
 try {const res=response();await handler({method:'POST',body:{url:'https://instagram.com/reel/ABCDE/'},headers:{}},res);assert.equal(res.code,200);assert.equal(res.body.media[0].type,'video');}
 finally {globalThis.fetch=oldFetch;for(const [key,value] of [['APIFY_TOKEN',oldToken],['DOWNLOADS_ENABLED',oldEnabled]]) if(value===undefined)delete process.env[key];else process.env[key]=value;}
});
