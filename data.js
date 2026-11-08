/* Data rules shared by the UI and deterministic Node tests. */
(function(root){
  'use strict';
  const DAY=/^\d{4}-\d{2}-\d{2}$/;
  const TIME=/^(?:[01]\d|2[0-3]):[0-5]\d$/;
  const fresh=(value,now,limit=2)=>Number.isFinite(Date.parse(value))&&Date.parse(value)<=now+300000&&now-Date.parse(value)<=limit*3600000;
  const dateAt=value=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Jerusalem',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
  const timeAt=value=>new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jerusalem',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value));
  function validate(data){
    if(!data||data.schema!==2||!Array.isArray(data.games)||!Array.isArray(data.sources)||!data.coverage)throw Error('Invalid schedule');
    if(!DAY.test(data.coverage.start)||!DAY.test(data.coverage.through))throw Error('Invalid coverage');
    const seen=new Set();
    for(const g of data.games){
      if(!g.id||seen.has(g.id)||!DAY.test(g.d)||!g.t||typeof g.t.he!=='string'||typeof g.c!=='boolean'||!Array.isArray(g.sources))throw Error('Invalid event');
      seen.add(g.id);
      if(g.k&&!TIME.test(g.k))throw Error('Invalid kickoff');
      if(g.start||g.end){
        if(!Number.isFinite(Date.parse(g.start))||!Number.isFinite(Date.parse(g.end))||Date.parse(g.end)<=Date.parse(g.start))throw Error('Invalid event window');
      }
    }
    if(data.nearby_advisories!==undefined){
      if(!Array.isArray(data.nearby_advisories))throw Error('Invalid advisories');
      const ids=new Set();
      for(const a of data.nearby_advisories){
        if(!a.id||ids.has(a.id)||!DAY.test(a.d)||!DAY.test(a.through)||a.through<a.d||a.parking_impact!=='unmeasured'||!a.t?.he||!a.venue?.he||!Array.isArray(a.references)||!a.references.length||!Number.isFinite(Date.parse(a.verified_at)))throw Error('Invalid advisory');
        if(a.k&&!TIME.test(a.k))throw Error('Invalid advisory time');
        if((a.start||a.end)&&(!Number.isFinite(Date.parse(a.start))||!Number.isFinite(Date.parse(a.end))||Date.parse(a.end)<=Date.parse(a.start)))throw Error('Invalid advisory window');
        ids.add(a.id);
      }
    }
    return data;
  }
  function sourceFresh(data,id,now){const s=data.sources.find(s=>s.id===id);return !!s&&['ok','partial'].includes(s.status)&&fresh(s.last_success,now,2)}
  // Published fixtures do not expire because a refresh is late. Retain actual
  // evidence, including cached successful responses; freshness is disclosure only.
  function sourceUsable(data,id,now){const s=data.sources.find(s=>s.id===id);return !!s&&['ok','partial','error'].includes(s.status)&&Number.isFinite(Date.parse(s.last_success))&&Date.parse(s.last_success)<=now+300000}
  function sourceComplete(s){return s.status==='ok'||(s.status==='error'&&s.last_success_status==='ok')}
  function coverageHealth(data,day,now=Date.now()){
    if(!data||day<data.coverage.start||day>data.coverage.through)return {usable:false,publishers:0,partial:true};
    const groups=new Set(data.sources.filter(s=>sourceComplete(s)&&sourceUsable(data,s.id,now)).map(s=>s.publisher||({stadium_sports:'stadium',stadium_culture:'stadium',ifa_maccabi:'ifa',ifa_hapoel:'ifa'}[s.id]||s.id)));
    const stadiumGroups=[...groups].filter(p=>['stadium','city','maccabi','ifa'].includes(p));
    // Two independent publishers, including an operator or city-wide calendar.
    // A duplicate feed or a nightclub alone cannot establish stadium coverage.
    return {usable:stadiumGroups.length>=2&&(groups.has('stadium')||groups.has('city')),publishers:groups.size,
      delayed:data.sources.some(s=>sourceComplete(s)&&sourceUsable(data,s.id,now)&&!sourceFresh(data,s.id,now)),
      partial:data.sources.some(s=>s.status!=='ok'||!sourceFresh(data,s.id,now))};
  }
  function coverageFresh(data,day,now=Date.now()){return coverageHealth(data,day,now).usable}
  function eventsForDay(data,day){
    return (data?.games||[]).filter(g=>g.start&&g.end?dateAt(g.start)<=day&&dateAt(Date.parse(g.end)-1)>=day:g.d===day);
  }
  function advisoriesForDay(data,day){
    return (data?.nearby_advisories||[]).filter(a=>a.start&&a.end?dateAt(a.start)<=day&&dateAt(Date.parse(a.end)-1)>=day:a.d<=day&&a.through>=day);
  }
  function windows(events,day){
    const intervals=events.filter(g=>g.start&&g.end).map(g=>[dateAt(g.start)<day?'00:00':timeAt(g.start),dateAt(g.end)>day?'24:00':timeAt(g.end)]).sort((a,b)=>a[0].localeCompare(b[0]));
    const out=[];
    for(const interval of intervals){const prev=out[out.length-1];if(prev&&interval[0]<=prev[1])prev[1]=prev[1]>interval[1]?prev[1]:interval[1];else out.push([...interval])}
    return out;
  }
  function assess(data,day,now=Date.now()){
    if(!data)return {state:'unknown',events:[],windows:[],reason:'unavailable'};
    const events=eventsForDay(data,day),ranges=windows(events,day);
    if(events.length){
      const confirmed=events.filter(g=>g.c&&g.start&&!g.conflict&&g.sources.some(id=>sourceUsable(data,id,now)));
      if(confirmed.length)return {state:'busy',events,delayed:confirmed.some(g=>!g.sources.some(id=>sourceFresh(data,id,now))),windows:windows(confirmed,day),reason:confirmed.length<events.length?'additionalPlanned':''};
      const conflict=events.some(g=>g.conflict);
      const aged=events.some(g=>!g.sources.some(id=>sourceUsable(data,id,now)));
      return {state:'tentative',events,windows:ranges,reason:aged?'stale':conflict?'conflict':'tentative'};
    }
    const health=coverageHealth(data,day,now);
    const distant=day>(data.coverage.detailed_through||new Date(Date.parse(data.coverage.start+'T12:00:00Z')+14*86400000).toISOString().slice(0,10));
    return health.usable?{state:'clear',delayed:health.delayed,events:[],windows:[],reason:distant?'provisional':health.partial?'partial':'',confidence:distant?'provisional':health.partial?'moderate':'higher',publishers:health.publishers}:{state:'unknown',events:[],windows:[],reason:day>data.coverage.through?'horizon':'stale'};
  }
  root.ParkingData={validate,fresh,dateAt,timeAt,sourceFresh,sourceUsable,coverageHealth,coverageFresh,eventsForDay,advisoriesForDay,windows,assess};
  if(typeof module!=='undefined')module.exports=root.ParkingData;
})(typeof window!=='undefined'?window:globalThis);
