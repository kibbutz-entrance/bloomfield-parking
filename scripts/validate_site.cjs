/* Validate the generated package, not just parser fixtures. No network required. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {validate} = require('../data.js');
function validateSite(dir, cacheFile, now=Date.now()) {
  const read = name => fs.readFileSync(path.join(dir,name));
  for(const name of ['index.html','share.html','data.js','games.json','parking-logo.png','parking-share-v2.jpg','.nojekyll']) read(name);
  assert(read('parking-logo.png').subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])), 'Invalid PNG');
  assert(read('parking-share-v2.jpg').subarray(0,3).equals(Buffer.from([255,216,255])), 'Invalid JPEG');
  for(const name of ['index.html','share.html']) {
    const html=read(name).toString();
    for(const required of ['data.js','games.json','parking-logo.png','parking-share-v2.jpg','og:title','og:image']) assert(html.includes(required), `${name}: missing ${required}`);
  }
  const data=validate(JSON.parse(read('games.json')));
  const cache=JSON.parse(fs.readFileSync(cacheFile));
  const ids=['stadium_sports','stadium_culture','ifa_maccabi','ifa_hapoel','maccabi','city'];
  const timestamp = value => Number.isFinite(Date.parse(value)) && Date.parse(value)<=now+300000;
  assert(timestamp(data.last_attempt) && now-Date.parse(data.last_attempt)<30*60000, 'Snapshot must come from this build');
  assert(data.updated===null || timestamp(data.updated), 'Invalid data timestamp');
  assert.equal(data.timezone,'Asia/Jerusalem');
  assert.deepEqual(data.sources.map(s=>s.id).sort(), ids.slice().sort());
  assert.deepEqual(Object.keys(cache).sort(), ids.slice().sort());
  for(const s of data.sources) {
    assert(['ok','partial','error'].includes(s.status),'Invalid health status');
    assert(timestamp(s.checked_at),'Invalid source check time');
    assert(s.last_success==null || timestamp(s.last_success),'Invalid success time');
    if(s.status!=='error') assert.equal(s.last_success,s.checked_at,'Fresh responses require fresh evidence');
    assert.equal(cache[s.id].status,s.status);
    assert.equal(cache[s.id].last_success,s.last_success);
    assert(Array.isArray(cache[s.id].records));
  }
  for(const g of data.games) {
    assert(g.sources.length && g.sources.every(id=>ids.includes(id)),'Unknown event source');
    assert(g.d>=data.coverage.start && g.d<=data.coverage.through,'Event outside coverage');
  }
  // Source outages are valid health data. They must still be published.
  return data;
}
if(require.main===module) { const d=validateSite(process.argv[2]||'dist',process.argv[3]||'data/source-cache.json'); console.log(`Validated publication: ${d.games.length} events, attempt ${d.last_attempt}`); }
module.exports={validateSite};
