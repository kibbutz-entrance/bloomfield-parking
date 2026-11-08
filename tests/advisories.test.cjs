const {test}=require('node:test');
const assert=require('node:assert/strict');
const P=require('../data.js');
const reviewed=require('./fixtures/data/nearby-advisories.json').advisories;
const snapshot=require('../games.json');
const now=Date.parse(snapshot.last_attempt);
const data=()=>({...structuredClone(snapshot),nearby_advisories:structuredClone(reviewed)});
test('night work appears on both calendar days, ending at 05:00',()=>{
 const d=data(),events=P.advisoriesForDay(d,'2026-11-09').filter(x=>x.kind==='access');
 assert.equal(events.length,2);assert.deepEqual(P.windows(events,'2026-11-09'),[['00:00','05:00'],['19:00','24:00']]);
});
test('nearby parties cannot turn green days red or establish missing core coverage',()=>{
 const d=data();assert.equal(P.assess(d,'2026-11-13',now).state,P.assess(snapshot,'2026-11-13',now).state);
 assert(P.advisoriesForDay(d,'2026-11-13').length>=2);
 d.sources=[];assert.equal(P.assess(d,'2026-11-13',now).state,'unknown');
});
test('advisories never become calendar-exportable matches or change confirmed match windows',()=>{
 const d=data();assert.deepEqual(d.games,snapshot.games);assert.deepEqual(P.assess(d,'2026-11-28',now),P.assess(snapshot,'2026-11-28',now));
});
test('protected all-day calendar span remains visible without invented times',()=>{
 const a=P.advisoriesForDay(data(),'2026-11-14').find(x=>x.id==='gagarin-insomnia');assert(a);assert.equal(a.k,'');assert.equal(a.start,null);
});
test('old clients without advisory fields and malformed advisory payloads are handled',()=>{
 const legacy=structuredClone(snapshot);delete legacy.nearby_advisories;
 assert.doesNotThrow(()=>P.validate(legacy));assert.deepEqual(P.advisoriesForDay(legacy,'2026-11-13'),[]);
 const d=data();d.nearby_advisories[0].parking_impact='verified';assert.throws(()=>P.validate(d));
});
