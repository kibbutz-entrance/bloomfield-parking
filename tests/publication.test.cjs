const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {validateSite}=require('../scripts/validate_site.cjs');
const root=path.join(__dirname,'..');
function fixture(run) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'parking-site-'));
  try {
    for(const file of ['index.html','data.js','games.json','parking-logo.png','parking-share-v2.jpg','.nojekyll']) fs.copyFileSync(path.join(root,file),path.join(dir,file));
    fs.copyFileSync(path.join(root,'index.html'),path.join(dir,'share.html'));
    const cacheFile=path.join(dir,'cache.json');
    fs.copyFileSync(path.join(root,'data/source-cache.json'),cacheFile);
    const data=JSON.parse(fs.readFileSync(path.join(dir,'games.json')));
    const now=Date.parse(data.last_attempt);
    const save=()=>fs.writeFileSync(path.join(dir,'games.json'),JSON.stringify(data));
    run({dir,cacheFile,data,now,save});
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
}
test('actual complete package validates',()=>fixture(({dir,cacheFile,now})=>assert(validateSite(dir,cacheFile,now))));
test('stale generated package cannot deploy',()=>fixture(({dir,cacheFile,now})=>assert.throws(()=>validateSite(dir,cacheFile,now+31*60000))));
test('missing share image blocks publication',()=>fixture(({dir,cacheFile,now})=>{fs.unlinkSync(path.join(dir,'parking-share-v2.jpg'));assert.throws(()=>validateSite(dir,cacheFile,now));}));
test('malformed generated event blocks publication',()=>fixture(({dir,cacheFile,data,now,save})=>{data.games[0].end='invalid';save();assert.throws(()=>validateSite(dir,cacheFile,now));}));
test('cache and public health must agree',()=>fixture(({dir,cacheFile,now})=>{const c=JSON.parse(fs.readFileSync(cacheFile));c.city.status='error';fs.writeFileSync(cacheFile,JSON.stringify(c));assert.throws(()=>validateSite(dir,cacheFile,now));}));
test('total source outage is publishable without inventing fresh success',()=>fixture(({dir,cacheFile,data,now,save})=>{
  const c=JSON.parse(fs.readFileSync(cacheFile));
  for(const s of data.sources){s.status='error';c[s.id].status='error';}
  data.coverage.complete=false;save();fs.writeFileSync(cacheFile,JSON.stringify(c));
  assert(validateSite(dir,cacheFile,now));
}));

test('an overnight event beginning yesterday still belongs to today',()=>fixture(({dir,cacheFile,data,now,save})=>{
  const today=data.coverage.start;
  const yesterday=new Date(Date.parse(today+'T12:00:00Z')-86400000).toISOString().slice(0,10);
  data.games[0].d=yesterday;
  data.games[0].start=yesterday+'T23:00:00+02:00';
  data.games[0].end=today+'T02:00:00+02:00';
  save();assert(validateSite(dir,cacheFile,now));
}));
