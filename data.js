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
    return data;
  }
  function sourceFresh(data,id,now){const s=data.sources.find(s=>s.id===id);return !!s&&s.status==='ok'&&fresh(s.last_success,now,2)}
  function coverageFresh(data,day,now=Date.now()){
    const required=['stadium_sports','stadium_culture','maccabi','city'];
    return !!data&&data.coverage.complete&&day>=data.coverage.start&&day<=data.coverage.through&&required.every(id=>sourceFresh(data,id,now));
  }
  function eventsForDay(data,day){
    return (data?.games||[]).filter(g=>g.start&&g.end?dateAt(g.start)<=day&&dateAt(Date.parse(g.end)-1)>=day:g.d===day);
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
      const conflict=events.some(g=>g.conflict);
      const aged=events.some(g=>!g.sources.some(id=>sourceFresh(data,id,now)));
      const tentative=conflict||aged||events.some(g=>!g.c||!g.start);
      return {state:tentative?'tentative':'busy',events,windows:ranges,reason:aged?'stale':conflict?'conflict':tentative?'tentative':''};
    }
    return coverageFresh(data,day,now)?{state:'clear',events:[],windows:[],reason:''}:{state:'unknown',events:[],windows:[],reason:day>data.coverage.through?'horizon':'stale'};
  }
  root.ParkingData={validate,fresh,dateAt,timeAt,coverageFresh,eventsForDay,windows,assess};
  if(typeof module!=='undefined')module.exports=root.ParkingData;
})(typeof window!=='undefined'?window:globalThis);
