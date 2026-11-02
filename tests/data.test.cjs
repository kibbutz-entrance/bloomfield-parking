const {test}=require('node:test');
const assert=require('node:assert/strict');
const P=require('../data.js');
const now=Date.parse('2026-11-02T12:00:00Z');
function data(games=[]){return {schema:2,games,coverage:{start:'2026-11-02',through:'2026-11-16',complete:true},sources:['stadium_sports','stadium_culture','ifa_maccabi','ifa_hapoel','maccabi','city'].map(id=>({id,status:'ok',last_success:'2026-11-02T11:55:00Z'}))}}
function game(overrides={}){return {id:'fixture-1',d:'2026-11-06',k:'23:30',start:'2026-11-06T20:30:00+02:00',end:'2026-11-07T02:00:00+02:00',t:{he:'משחק'},c:true,sources:['ifa_maccabi'],...overrides}}
test('never show an all-clear while loading or after complete failure',()=>assert.equal(P.assess(null,'2026-11-02',now).state,'unknown'));
test('fresh official coverage permits a probable clear day',()=>assert.equal(P.assess(data(),'2026-11-03',now).state,'clear'));
test('city API is essential even when optional IFA feeds are available',()=>{let d=data();d.sources.find(s=>s.id==='city').status='error';assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});
test('optional IFA failure is visible without disabling verified core coverage',()=>{let d=data();d.sources.find(s=>s.id==='ifa_hapoel').status='error';assert.equal(P.assess(d,'2026-11-03',now).state,'clear')});
test('old data cannot show green',()=>assert.equal(P.assess(data(),'2026-11-03',now+3*3600000).state,'unknown'));
test('missing required source cannot show green',()=>{let d=data();d.sources[0].status='error';assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});
test('unpublished distant schedule cannot show green',()=>assert.equal(P.assess(data(),'2027-02-01',now).state,'unknown'));
test('nearby source update cannot hide a failed older required source',()=>{let d=data();d.sources[0].last_success='2026-10-30T00:00:00Z';assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});
test('data with a future timestamp cannot show green',()=>{let d=data();d.sources[0].last_success='2026-11-03T00:00:00Z';assert.equal(P.assess(d,'2026-11-03',now).state,'unknown')});
test('midnight event covers both dates',()=>{let d=data([game()]);assert.equal(P.assess(d,'2026-11-07',now).state,'busy');assert.deepEqual(P.windows(d.games,'2026-11-07'),[['00:00','02:00']])});
test('end at midnight does not occupy the following day',()=>{let d=data([game({end:'2026-11-07T00:00:00+02:00'})]);assert.equal(P.eventsForDay(d,'2026-11-07').length,0)});
test('unannounced kickoff stays tentative',()=>assert.equal(P.assess(data([game({start:null,end:null,k:'',c:false})]),'2026-11-06',now).state,'tentative'));
test('conflicting sources stay tentative',()=>assert.equal(P.assess(data([game({conflict:true})]),'2026-11-06',now).state,'tentative'));
test('stale known event is explicitly uncertain',()=>assert.equal(P.assess(data([game()]),'2026-11-06',now+3*3600000).reason,'stale'));
test('separate events do not invent a continuous all-day window',()=>{let games=[game({start:'2026-11-06T08:00:00+02:00',end:'2026-11-06T10:00:00+02:00'}),game({id:'2',start:'2026-11-06T18:00:00+02:00',end:'2026-11-06T20:00:00+02:00'})];assert.deepEqual(P.windows(games,'2026-11-06'),[['08:00','10:00'],['18:00','20:00']])});
test('invalid or legacy JSON cannot become authoritative data',()=>{assert.throws(()=>P.validate({games:[]}));assert.throws(()=>P.validate(data([game({end:'bad'})])))});
test('Israeli day is independent of the browser time zone',()=>assert.equal(P.dateAt('2026-11-02T23:15:00Z'),'2026-11-03'));
