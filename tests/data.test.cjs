const {test}=require('node:test');
const assert=require('node:assert/strict');
const P=require('../data.js');
const now=Date.parse('2026-11-02T12:00:00Z');
function data(games=[]){return {schema:2,games,coverage:{start:'2026-11-02',through:'2027-11-02',detailed_through:'2026-11-16',complete:true},sources:['stadium_sports','stadium_culture','ifa_maccabi','ifa_hapoel','maccabi','city'].map(id=>({id,status:'ok',last_success:'2026-11-02T11:55:00Z'}))}}
function game(overrides={}){return {id:'fixture-1',d:'2026-11-06',k:'23:30',start:'2026-11-06T20:30:00+02:00',end:'2026-11-07T02:00:00+02:00',t:{he:'משחק'},c:true,sources:['ifa_maccabi'],...overrides}}
test('never show an all-clear while loading or after complete failure',()=>assert.equal(P.assess(null,'2026-11-02',now).state,'unknown'));
test('fresh official coverage permits a probable clear day',()=>assert.equal(P.assess(data(),'2026-11-03',now).state,'clear'));
test('one failed city feed still permits a qualified estimate from independent schedules',()=>{let d=data();d.sources.find(s=>s.id==='city').status='error';assert.equal(P.assess(d,'2026-11-03',now).state,'clear');assert.equal(P.assess(d,'2026-11-03',now).reason,'partial')});
test('optional IFA failure is visible without disabling verified core coverage',()=>{let d=data();d.sources.find(s=>s.id==='ifa_hapoel').status='error';assert.equal(P.assess(d,'2026-11-03',now).state,'clear')});
test('old data cannot show green',()=>assert.equal(P.assess(data(),'2026-11-03',now+25*3600000).state,'unknown'));
test('one missing operator feed does not blank all no-event days',()=>{let d=data();d.sources[0].status='error';assert.equal(P.assess(d,'2026-11-03',now).state,'clear')});
test('distant dates get a provisional estimate from published schedules',()=>{assert.equal(P.assess(data(),'2027-02-01',now).state,'clear');assert.equal(P.assess(data(),'2027-02-01',now).reason,'provisional')});
test('an old source lowers certainty while other independent publishers work',()=>{let d=data();d.sources[0].last_success='2026-10-30T00:00:00Z';assert.equal(P.assess(d,'2026-11-03',now).reason,'partial')});
test('data with a future timestamp cannot show green',()=>{let d=data();d.sources.forEach(s=>s.last_success='2026-11-03T00:00:00Z');assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});
test('midnight event covers both dates',()=>{let d=data([game()]);assert.equal(P.assess(d,'2026-11-07',now).state,'busy');assert.deepEqual(P.windows(d.games,'2026-11-07'),[['00:00','02:00']])});
test('end at midnight does not occupy the following day',()=>{let d=data([game({end:'2026-11-07T00:00:00+02:00'})]);assert.equal(P.eventsForDay(d,'2026-11-07').length,0)});
test('unannounced kickoff stays tentative',()=>assert.equal(P.assess(data([game({start:null,end:null,k:'',c:false})]),'2026-11-06',now).state,'tentative'));
test('conflicting sources stay tentative',()=>assert.equal(P.assess(data([game({conflict:true})]),'2026-11-06',now).state,'tentative'));
test('stale known event is explicitly uncertain',()=>assert.equal(P.assess(data([game()]),'2026-11-06',now+25*3600000).reason,'stale'));
test('separate events do not invent a continuous all-day window',()=>{let games=[game({start:'2026-11-06T08:00:00+02:00',end:'2026-11-06T10:00:00+02:00'}),game({id:'2',start:'2026-11-06T18:00:00+02:00',end:'2026-11-06T20:00:00+02:00'})];assert.deepEqual(P.windows(games,'2026-11-06'),[['08:00','10:00'],['18:00','20:00']])});
test('invalid or legacy JSON cannot become authoritative data',()=>{assert.throws(()=>P.validate({games:[]}));assert.throws(()=>P.validate(data([game({end:'bad'})])))});
test('Israeli day is independent of the browser time zone',()=>assert.equal(P.dateAt('2026-11-02T23:15:00Z'),'2026-11-03'));

test('two feeds from the same publisher are not independent coverage',()=>{let d=data();d.sources.forEach(s=>{if(!s.id.startsWith('stadium'))s.status='error'});assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});
test('two team feeds without an operator or city calendar do not establish coverage',()=>{let d=data();d.sources.forEach(s=>{if(!s.id.startsWith('ifa')&&s.id!=='maccabi')s.status='error'});assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});
test('a nearby club cannot replace stadium coverage',()=>{let d=data();d.sources.forEach(s=>s.status='error');d.sources.push({id:'haoman',publisher:'haoman',status:'ok',last_success:'2026-11-02T11:55:00Z'});assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});
test('actual distant planned fixtures still prevent a green day',()=>assert.equal(P.assess(data([game({d:'2027-02-01',start:null,end:null,k:'',c:false})]),'2027-02-01',now).state,'tentative'));
test('dates beyond the supported year remain unknown',()=>assert.equal(P.assess(data(),'2028-02-01',now).state,'unknown'));

test('a confirmed congestion window is useful even with another tentative event',()=>{let d=data([game(),game({id:'planned',start:null,end:null,k:'',c:false})]);let a=P.assess(d,'2026-11-06',now);assert.equal(a.state,'busy');assert.equal(a.reason,'additionalPlanned');assert.deepEqual(a.windows,[['20:30','24:00']])});
test('partial parsing can support a verified event but cannot establish absence',()=>{let d=data([game({sources:['haoman']})]);d.sources.forEach(s=>s.status='error');d.sources.push({id:'haoman',publisher:'haoman',status:'partial',last_success:'2026-11-02T11:55:00Z'});assert.equal(P.assess(d,'2026-11-06',now).state,'busy');assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});

// Reproduce observed GitHub schedule gaps without relabelling old checks fresh.
test('scheduler gaps keep a bounded, explicitly delayed estimate',()=>{
  for(const hours of [3,7,12,23]){
    const d=data(), time=now+hours*3600000;
    const a=P.assess(d,'2026-11-03',time);
    assert.equal(a.state,'clear'); assert.equal(a.delayed,true);
    assert.equal(P.sourceFresh(d,'city',time),false);
  }
});
test('known congestion remains visible during a scheduler gap',()=>{
  const a=P.assess(data([game()]),'2026-11-06',now+7*3600000);
  assert.equal(a.state,'busy');assert.equal(a.delayed,true);
});
test('fresh updates remove delay warning',()=>assert.equal(P.assess(data(),'2026-11-03',now).delayed,false));
test('grace period never masks observed source failures',()=>{
  const d=data();d.sources.forEach(s=>s.status='error');
  assert.equal(P.assess(d,'2026-11-03',now+7*3600000).state,'unknown');
});
test('delay cannot override conflicting event details',()=>{
  assert.equal(P.assess(data([game({conflict:true})]),'2026-11-06',now+7*3600000).state,'tentative');
});
test('24 hour limit uses actual source success, including its exact boundary',()=>{
  const d=data(), time=Date.parse(d.sources[0].last_success)+24*3600000;
  assert.equal(P.assess(d,'2026-11-03',time).state,'clear');
  assert.equal(P.assess(d,'2026-11-03',time+1).state,'unknown');
});
