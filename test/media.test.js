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
function response(){return {headers:{},setHeader(k,v){this.headers[k]=v;},status(code){this.code=code;return this;},json(body){this.body=body;return this;},end(){this.ended=true;}};}
test('legacy route redirects POST to the API-free extractor',()=>{
 const res=response();handler({method:'POST'},res);assert.equal(res.code,307);assert.equal(res.headers.Location,'/api/direct');assert.equal(res.ended,true);
 const get=response();handler({method:'GET'},get);assert.equal(get.code,405);
});