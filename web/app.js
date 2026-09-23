/**
 * Browser UI for the job-fit workbench: collect inputs, review requirements,
 * display assessments, and export or restore user-managed files.
 * Scoring and document parsing are delegated to the Python worker through
 * request IDs. Candidate text stays in memory unless the user downloads it;
 * rendered evidence uses text nodes rather than HTML interpolation.
 */
'use strict';
const $=id=>document.getElementById(id);
const categories=['Leadership','Architecture and technical skills','Delivery and collaboration','Reliability and security','AI and developer productivity','Business and domain'];
let worker, ready=false, counter=0, requirements=[], report=null, lastInputs=null, pending=new Map();
function error(message){$('error').textContent=message;$('error').hidden=!message;}
function status(message){$('status').textContent=message;}
/** Initialize the Python worker and route replies to pending UI requests. */
function startWorker(){
 worker=new Worker('worker.js',{type:'module'});
 worker.onmessage=({data})=>{
  if(data.type==='ready'){ready=true;$('analyze').disabled=false;status('Ready. All document processing happens on this device.');return;}
  if(data.type==='fatal'){error('Python could not load. Check your connection and reload. '+data.error);status('Engine unavailable');return;}
  const call=pending.get(data.id);if(!call)return;pending.delete(data.id);clearTimeout(call.timer);
  data.error?call.reject(new Error(data.error)):call.resolve(data.result);
 };
 worker.onerror=event=>{error('The Python worker stopped. Reload to restart. '+event.message);$('analyze').disabled=true;};
}
startWorker();
function rpc(payload){return new Promise((resolve,reject)=>{
 const id=++counter;
 const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Processing timed out. Try a smaller document or reload.'));},90000);
 pending.set(id,{resolve,reject,timer});worker.postMessage({id,payload});
});}
function values(){return {job:$('job').value,resume:$('resume').value,experiences:$('experience').value,metadata:{role:$('role').value,company:$('company').value,url:$('url').value,baseline:$('baseline').value||'Pasted resume'}};}
function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function labeled(title,element){const label=node('label',title);label.append(element);return label;}
function select(options,value,onchange){const e=node('select');for(const [v,t] of options){const o=node('option',t);o.value=v;e.append(o);}e.value=value;e.onchange=()=>onchange(e.value);return e;}
function download(name,data,type){const u=URL.createObjectURL(new Blob([data],{type}));const a=node('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function invalidate(){report=null;$('results').hidden=true;}
/** Build editable requirement cards with source excerpts and review controls. */
function renderReview(result){
 const container=$('review');container.replaceChildren();
 const lookup=new Map([...(result?.requirements||[]),...(result?.eligibility||[])].map(r=>[r.id,r]));
 for(const req of requirements){
  const matched=lookup.get(req.id);
  const card=node('article',undefined,'requirement');
  const header=node('div',undefined,'req-head');header.append(node('strong',req.concept||'Review this requirement'));
  const remove=node('button','Remove','subtle');remove.setAttribute('aria-label','Remove '+(req.concept||req.text));remove.onclick=()=>{requirements=requirements.filter(r=>r.id!==req.id);invalidate();renderReview(result);};header.append(remove);card.append(header);
  const text=node('textarea');text.className='req-text';text.value=req.text;text.rows=2;text.onchange=()=>{req.text=text.value;req.reviewed=false;req.concept='';invalidate();};card.append(labeled('Requirement from posting',text));
  const grid=node('div',undefined,'req-grid');
  grid.append(labeled('Importance',select([['core','Core requirement'],['preferred','Preferred qualification'],['eligibility','Eligibility / practical condition']],req.importance,v=>{req.importance=v;req.reviewed=false;invalidate();renderReview(result);}))) ;
  if(req.importance==='eligibility'){
   grid.append(labeled('Eligibility status',select([['unknown','Unknown — confirm'],['met','Met'],['unmet','Unmet']],req.gate_status||'unknown',v=>{req.gate_status=v;invalidate();})));
  }else{
   grid.append(labeled('Category',select(categories.map(c=>[c,c]),categories.includes(req.category)?req.category:categories[2],v=>{req.category=v;invalidate();})));
   const level=select([['0','0% · Not evidenced'],['0.25','25% · Keyword only'],['0.5','50% · Partial / transferable'],['0.75','75% · Substantial evidence'],['1','100% · Demonstrated']],String(req.level??matched?.level??0),v=>{req.level=Number(v);invalidate();});
   level.dataset.level=req.id;grid.append(labeled('Evidence credit',level));
  }
  card.append(grid);
  if(matched?.evidence?.length){
   for(const ev of matched.evidence){const q=node('div',undefined,'quote');q.append(node('b',ev.source),node('span',ev.text));card.append(q);}
  }else if(req.importance!=='eligibility'){card.append(node('p',matched?.reason||'No automatic supporting excerpt. Add a rationale if you have evidence.','hint'));}
  const reason=node('textarea');reason.rows=2;reason.placeholder='Explain the match, gap, or eligibility answer. Cite the relevant example and scope.';reason.value=req.reason||'';reason.oninput=()=>{req.reason=reason.value;invalidate();};card.append(labeled('Your rationale',reason));
  if(req.importance!=='eligibility'){
   const check=node('input');check.type='checkbox';check.checked=!!req.reviewed;
   check.onchange=()=>{req.reviewed=check.checked;req.level=Number(card.querySelector('[data-level]').value);invalidate();};
   const label=node('label',undefined,'reviewed-label');label.append(check,node('span','I reviewed this requirement and its supporting evidence'));card.append(label);
  }
  container.append(card);
 }
 $('review-section').hidden=false;
}
/** Draft the rubric and suggested evidence before the user calculates results. */
async function build(){
 error('');$('analyze').disabled=true;status('Extracting requirements and finding supporting evidence…');
 try{
  const input=values();
  const result=await rpc({action:'score',...input});
  requirements=[...result.requirements.map(r=>({id:r.id,text:r.text,concept:r.concept,category:r.category,importance:r.importance,reviewed:false,level:r.level,reason:'',gate_status:'unknown'})),...result.eligibility.map(r=>({id:r.id,text:r.text,concept:'',category:'Eligibility',importance:'eligibility',gate_status:'unknown',reason:''}))];
  lastInputs=input;invalidate();renderReview(result);status('Draft ready. Review the extracted requirements before interpreting the score.');
  $('review-section').scrollIntoView({behavior:'smooth'});
 }catch(e){error(e.message);status('Assessment could not be built.');}
 finally{$('analyze').disabled=!ready;}
}
$('analyze').onclick=build;
$('add').onclick=()=>{requirements.push({id:'manual-'+Date.now(),text:'Add the exact requirement here',concept:'',category:categories[2],importance:'core',reviewed:false,level:0,reason:''});invalidate();renderReview();};
function showResult(result,baseline){
 report={...result,baseline_score:baseline.score,baseline_note:'Resume-only automatic estimate using the same requirements, without manual broader-profile overrides.'};
 $('score').textContent=result.rounded_score;$('recommendation').textContent=result.recommendation;
 $('confidence').textContent=`${result.confidence} · ${result.reviewed_count}/${result.requirement_count} scored requirements reviewed`;
 $('baseline-score').textContent=baseline.rounded_score+'/100 (auto)';
 $('categories').replaceChildren();
 for(const cat of result.categories){const row=node('div',undefined,'barrow');const label=node('div',undefined,'barlabel');label.append(node('span',cat.category),node('strong',cat.earned+' / '+cat.weight));const bar=node('div',undefined,'bar');const fill=node('span');fill.style.width=(cat.earned/cat.weight*100)+'%';bar.append(fill);row.append(label,bar);$('categories').append(row);}
 $('strengths').replaceChildren();$('gaps').replaceChildren();
 const strong=result.requirements.filter(r=>r.level>=.75).sort((a,b)=>b.level-a.level).slice(0,5);
 for(const r of strong)$('strengths').append(node('li',(r.concept||r.text)+' — '+(r.evidence[0]?.text||r.reason)));
 if(!strong.length)$('strengths').append(node('li','No substantial evidence found yet. Review the resume text and add supported examples.'));
 const gaps=result.requirements.filter(r=>r.level<.75).sort((a,b)=>(a.importance==='core'?-1:1)-(b.importance==='core'?-1:1)||a.level-b.level).slice(0,7);
 for(const r of gaps)$('gaps').append(node('li',(r.concept||r.text)+' — '+r.status+'. '+r.reason));
 if(!gaps.length)$('gaps').append(node('li','No major evidence gaps under the current rubric. Check scope, recency and omitted requirements.'));
 $('gates').replaceChildren();
 for(const g of result.eligibility){const p=node('div',undefined,'gate');p.append(node('span',g.status,'badge'),node('span',g.text));if(g.reason)p.append(node('p',g.reason,'hint'));$('gates').append(p);}
 if(!result.eligibility.length)$('gates').append(node('p','No eligibility conditions were detected. Review location, travel, authorization, education and experience thresholds manually.'));
 $('method').textContent=result.methodology+' Displayed total: '+result.score+'/100 before whole-number rounding. Category weights are normalized across detected categories; preferred qualifications never exceed 15 points.';
 $('results').hidden=false;
}
// Score the reviewed profile and a separate automatic resume-only baseline.
$('calculate').onclick=async()=>{
 error('');$('calculate').disabled=true;
 try{
  const input=values();
  if(JSON.stringify(input)!==JSON.stringify(lastInputs))throw new Error('Your inputs changed. Build a new evidence review first.');
  const result=await rpc({action:'score',...input,requirements});
  const baseline=await rpc({action:'score',...input,experiences:'',requirements:requirements.map(r=>({...r,reviewed:false,level:null,reason:''}))});
  showResult(result,baseline);$('results').scrollIntoView({behavior:'smooth'});status('Assessment calculated. Export or review your evidence.');
 }catch(e){error(e.message);}finally{$('calculate').disabled=false;}
};
async function upload(event,target){
 const file=event.target.files[0];if(!file)return;error('');
 if(file.size>8*1024*1024){error('Use a file of 8 MB or less.');return;}
 if(!ready){error('Wait for the Python engine to load.');return;}
 status('Extracting your document locally…');$('analyze').disabled=true;
 try{
  const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
  const result=await rpc({action:'extract',name:file.name,content:btoa(binary)});
  $(target).value=result.text;if(target==='resume')$('baseline').value=file.name;requirements=[];invalidate();$('review-section').hidden=true;status('Document extracted. Check the text and reading order before scoring.');
 }catch(e){error(e.message);}finally{$('analyze').disabled=!ready;}
};
$('resume-file').onchange=e=>upload(e,'resume');
$('experience-file').onchange=e=>upload(e,'experience');
$('export').onclick=()=>{
 if(!report)return;
 let text=`# ${report.metadata.role||'Job fit assessment'}\n\nCompany: ${report.metadata.company||'Not supplied'}\nBaseline: ${report.metadata.baseline}\nSource URL: ${report.metadata.url||'Pasted job description'}\n\nEstimated match: ${report.score}/100\nResume-only automatic estimate: ${report.baseline_score}/100\nRecommendation: ${report.recommendation}\nConfidence: ${report.confidence}\n\n${report.methodology}\n\n## Categories\n`;
 for(const c of report.categories)text+=`\n- ${c.category}: ${c.earned}/${c.weight}`;
 text+='\n\n## Requirement evidence\n';
 for(const r of report.requirements){text+=`\n### ${r.concept||'Requirement'}\n${r.text}\n\n${r.status}; ${r.level*100}% credit; ${r.reviewed?'reviewed':'automatic'}\n${r.reason}\n`;for(const e of r.evidence)text+=`\n- ${e.source}: ${e.text}\n`;}
 text+='\n## Eligibility\n';for(const g of report.eligibility)text+=`\n- ${g.status}: ${g.text} ${g.reason}\n`;
 download('job-fit-report.md',text,'text/markdown');
};
// Persistence is explicit: save a local JSON file and validate it on restore.
$('save').onclick=()=>download('job-fit-assessment.json',JSON.stringify({schema_version:1,inputs:values(),requirements},null,2),'application/json');
$('load').onchange=async event=>{
 const file=event.target.files[0];if(!file)return;error('');
 try{
  if(file.size>3*1024*1024)throw new Error('Assessment file is too large.');
  const data=JSON.parse(await file.text());
  if(data.schema_version!==1||!data.inputs||!Array.isArray(data.requirements))throw new Error('Not a supported saved assessment.');
  for(const field of ['job','resume','experiences'])if(typeof data.inputs[field]!=='string'||data.inputs[field].length>150000)throw new Error('Invalid assessment text.');
  const result=await rpc({action:'score',...data.inputs,requirements:data.requirements});
  const input=data.inputs;for(const id of ['job','resume'])$(id).value=input[id];$('experience').value=input.experiences;
  for(const id of ['role','company','url','baseline'])$(id).value=String(input.metadata?.[id]||'');
  requirements=data.requirements;lastInputs=values();invalidate();renderReview(result);status('Assessment restored in memory. Calculate to refresh the report.');
 }catch(e){error(e.message);}
};
// Reset the UI and terminate the worker to discard its in-memory candidate data.
$('clear').onclick=()=>{
 for(const id of ['job','resume','experience','role','company','url','baseline','resume-file','experience-file','load'])$(id).value='';
 requirements=[];lastInputs=null;invalidate();$('review-section').hidden=true;$('review').replaceChildren();$('gates').replaceChildren();$('strengths').replaceChildren();$('gaps').replaceChildren();error('');
 worker.terminate();for(const call of pending.values()){clearTimeout(call.timer);call.reject(new Error('Data cleared.'));}pending.clear();ready=false;$('analyze').disabled=true;status('Cleared. Restarting Python…');startWorker();
};
$('demo').onclick=()=>{
 $('role').value='Engineering Manager';$('company').value='Example Systems (fictional)';$('baseline').value='Fictional sample resume';$('url').value='';
 $('job').value='Required qualifications\n7+ years of software engineering experience.\n2+ years of people management experience.\nLead teams and provide mentoring and career development.\nBuild reliable Python APIs and React applications.\nOwn CI/CD, automated testing and engineering roadmaps.\nLead incident response and disaster recovery.\nPartner with Product Management to improve internal tools.\nMust be authorized to work without sponsorship.\nPreferred qualifications\nExperience with FastAPI, Kubernetes and financial services.';
 $('resume').value='Fictional candidate\nEngineering Manager, Example Software, 2020-present\nLed a team of eight engineers and mentored two technical leads through career development plans.\nBuilt Python APIs for financial services applications, integrating operational data into internal tools.\nEstablished CI/CD pipelines and automated testing, reducing escaped defects by 20%.\nPartnered with Product Management on engineering roadmaps and release priorities.\nSkills: React, Docker, Kubernetes.';
 $('experience').value='Additional confirmed example: Led incident response for an application outage and introduced monitoring improvements after the review.';
 requirements=[];lastInputs=null;invalidate();$('review-section').hidden=true;status('Fictional example loaded. Build an evidence review to explore.');
};
for(const id of ['job','resume','experience','role','company','url','baseline'])$(id).addEventListener('input',()=>{invalidate();});

