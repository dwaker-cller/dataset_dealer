const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let records=[],currentOutput=null,exporting=false;
let info=null,result=null,running=false,paused=false,runId=0,filter='all',resultSheet='',toastTimer;
const steps=[['文件识别','目录与格式'],['Excel 提取','工作表与单元格'],['文档解析','PDF / Word'],['字段识别','按列字段定位'],['口径核对','OWL + 模板约束'],['模板回填','校验与输出']];
const methods={xls:'工作表解析',xlsx:'工作表解析',docx:'段落 / 表格解析',pdf:'文本解析 / OCR',png:'OCR 文字识别',jpg:'OCR 文字识别',jpeg:'OCR 文字识别'};
function payload(){return Object.fromEntries(['folder','template','owl'].map(k=>[k,$(k).value.trim()]));}
async function api(url,data){const r=await fetch(url,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const j=await r.json();if(!r.ok)throw Error(j.error||'请求失败');return j;}
function error(e){$('error').textContent=e.message||e;$('error').hidden=false;}
// Presentation pacing only; percentages are not measured backend work.
async function pacedRequest(request,token,points,onProgress){
 let done=false,value,failure;
 request.then(v=>{value=v;done=true;},e=>{failure=e;done=true;});
 const began=performance.now(),duration=points.at(-1)[0];
 while(token===runId){
  if(failure)throw failure;
  const elapsed=performance.now()-began;
  if(done&&elapsed>=duration)return value;
  let index=points.findIndex(p=>p[0]>elapsed);if(index<0)index=points.length-1;
  const left=points[Math.max(0,index-1)],right=points[index];
  const ratio=right[0]===left[0]?1:Math.min(1,Math.max(0,(elapsed-left[0])/(right[0]-left[0])));
  onProgress(Math.floor(left[1]+(right[1]-left[1])*ratio),elapsed>=duration);
  await new Promise(resolve=>setTimeout(resolve,80));
 }
 return null;
}
function toast(s){$('toast').textContent=s;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,3500);}
function tab(name,verificationColumn){if(name==='report')loadReports();if(name==='verification')loadVerification(verificationColumn);document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));['files','mapping','result','verification','report'].forEach(n=>$('pane-'+n).hidden=n!==name);document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));$(name==='files'?'nav-task':name==='mapping'?'nav-map':'nav-results').classList.add('active');}
function pipeline(index=-1){$('pipeline').innerHTML=steps.map((s,i)=>`<div class="stage ${i<index?'done':i===index?'active':''}"><span class="stage-icon">${i<index?'✓':String(i+1).padStart(2,'0')}</span><div class="stage-label">${s[0]}<small>${s[1]}</small></div></div>`).join('');}
function reset(){
 runId++;running=false;paused=false;currentOutput=null;
 $('export').disabled=exporting||!records.length;$('clear-results').disabled=exporting||!records.length;
 $('pause').hidden=true;$('cancel').hidden=true;$('run-state').textContent='待开始';$('percent').textContent='0%';
 $('progress-bar').style.width='0%';$('event-text').textContent='选择工程并检查配置后开始';$('start').textContent='开始抽取 →';
 pipeline();lock(false);
}
function lock(v){
 document.querySelectorAll('input:not(#search-file),[data-pick],#restore,#inspect').forEach(e=>e.disabled=v);
 $('start').disabled=v||!info;$('clear-results').disabled=v||exporting||!records.length;
}
function invalidate(){
 filter='all';$('search-file').value='';
 info=null;reset();$('start').disabled=true;$('ready-dot').className='dot busy';$('ready-text').textContent='配置待检查';
 $('ready-detail').textContent='选好三项路径后，点击“检查配置”';
 ['file-body','map-body','file-types','file-footer','map-sheet'].forEach(k=>$(k).innerHTML='');
 $('file-body').innerHTML='<tr><td colspan="6">数据源待检查，请点击“检查配置”加载当前文件夹的文件清单。</td></tr>';
 $('mapping-summary').textContent='检查配置后显示当前工作表的关联统计';
 $('folder-note').textContent='支持递归读取子文件夹';$('template-note').textContent='按模板字段确定抽取范围';$('owl-note').textContent='按指标定义约束取值口径';
}
async function inspect(){
 invalidate();lock(true);$('error').hidden=true;$('ready-text').textContent='正在检查';$('ready-detail').textContent='读取文件清单、模板表头和 OWL';
 const token=runId;
 try{
  const checked=await pacedRequest(api('/api/inspect',payload()),token,[[0,0],[800,23],[2200,48],[3500,78],[4500,96]],(percent,waiting)=>{
   $('ready-text').textContent=`正在检查 ${percent}%`;
   $('ready-detail').textContent=waiting?'等待配置检查返回':percent<30?'检查工程目录':percent<65?'检查模板与指标标准':'整理文件清单';
  });
  if(token!==runId)return;
  if(records.length&&records[0].contractKey!==checked.contractKey)throw Error('模板或 OWL 已改变。已有结果可继续导出；请清空累计结果后开始新批次。');
  info=checked;$('folder-note').textContent=`${info.files.length} 份可读文件 · 跳过 ${info.skipped} 份其他格式`;
  $('template-note').textContent=`${info.sheets.length} 个工作表 · 保留多级表头`;
  $('owl-note').textContent=`${info.definitions.length} 条指标定义 · 包含同名不同工程类型`;
  $('ready-dot').className='dot';$('ready-text').textContent='配置就绪';$('ready-detail').textContent='点击“开始抽取”追加当前工程';
  $('map-sheet').innerHTML=info.sheets.map(s=>`<option>${esc(s.name)}</option>`).join('');filter='all';renderFiles();renderMapping();
 }catch(e){info=null;error(e);$('ready-dot').className='dot error';$('ready-text').textContent='检查未通过';$('ready-detail').textContent='已有累计结果保留，可继续导出';}finally{lock(false);}
}
const fileStages=['前期与可研','初步设计','招标与合同','施工图与预算','施工与变更','竣工与验收','结算与审核','决算与审计','待归类'];
function renderFiles(){
 if(!info)return;
 const counts={};info.files.forEach(f=>{const stage=f.stage||'待归类';counts[stage]=(counts[stage]||0)+1;});
 $('file-types').innerHTML=`<button class="chip ${filter==='all'?'selected':''}" data-filter="all">全部 ${info.files.length}</button>`+fileStages.filter(k=>counts[k]).map(k=>`<button class="chip ${filter===k?'selected':''}" data-filter="${k}">${k} ${counts[k]}</button>`).join('');
 const q=$('search-file').value.toLowerCase();
 const files=info.files.filter(f=>(filter==='all'||(f.stage||'待归类')===filter)&&f.path.toLowerCase().includes(q));
 $('file-body').innerHTML=files.map(f=>`<tr><td><div class="filename"><div class="file-icon ${f.ext}">${f.ext.toUpperCase()}</div><div><span title="${esc(f.name)}">${esc(f.name)}</span><small title="${esc(f.path)}">${esc(f.path)}</small></div></div></td><td title="${esc(f.stageBasis||'')}">${esc(f.stage||'待归类')}</td><td>${f.ext.toUpperCase()}</td><td>${f.size>1048576?(f.size/1048576).toFixed(1)+' MB':Math.ceil(f.size/1024)+' KB'}</td><td>${methods[f.ext]}</td><td><span class="status ${currentOutput?'finished':''}">${currentOutput?(currentOutput.extraction.sources.some(p=>p.endsWith(f.path))?'已用于回填':(currentOutput.extraction.coverage?.files?.[f.path]?.label||'未纳入本轮')):running?'核对中':'待处理'}</span></td></tr>`).join('')||'<tr><td colspan="6">没有符合条件的文件</td></tr>';
 $('file-footer').textContent=`当前数据源：${info.project} · ${filter==='all'?'全部阶段':filter} · 显示 ${files.length} / ${info.files.length} 份支持格式文件 · 其他格式 ${info.skipped} 份未列入`;
}

function renderMapping(){if(!info)return;const s=info.sheets.find(s=>s.name===$('map-sheet').value)||info.sheets[0];$('mapping-summary').textContent=`${s.name}：已关联 ${s.fields.filter(f=>f.matches.length).length} / ${s.fields.length} 个字段`;$('map-body').innerHTML=s.fields.map((f,i)=>`<tr><td title="${esc(f.comment)}">${esc(f.column)} &nbsp; ${esc(f.label||'未命名字段')}</td><td>${f.matches.length?`<button class="maplink" data-field="${i}">${esc(f.matches[0].name)} ↗</button>`:'—'}</td><td>${esc(f.matches[0]?.standardUnit||'—')}</td><td><span class="status ${f.matches.length?'finished':''}">${f.matches.length===1?'已关联':f.matches.length>1?'多个适用定义':'待关联 / 基本信息'}</span></td></tr>`).join('');}
let detailProjectId='';
function detail(f,value,project=''){detailProjectId=records.find(r=>r.projectName===project)?.projectId||'';$('drawer-title').textContent=f.matches[0]?.name||f.chain.at(-1)||'模板字段';$('drawer-body').innerHTML=`${f.matches.map(d=>`<h3>指标编码</h3><code>${esc(d.identifier)} · ${esc(d.id)}</code><h3>定义</h3><p>${esc(d.definitionText)}</p><h3>业务口径</h3><p>${esc(d.applicability)}</p><h3>标准单位</h3><p>${esc(d.standardUnit)}</p>`).join('')}${f.comment?`<h3>模板批注</h3><p>${esc(f.comment)}</p>`:''}`;appendEvidence(f);if(project)$('drawer-body').insertAdjacentHTML('afterbegin',`<p class="detail-project">${esc(project)}</p>`);$('drawer-backdrop').hidden=false;$('close-drawer').focus();}
function renderResult(){if(!result)return;const s=result.sheets.find(s=>s.name===resultSheet)||result.sheets[0];resultSheet=s.name;$('sheet-tabs').innerHTML=result.sheets.map(s=>`<button class="chip ${s.name===resultSheet?'selected':''}" data-sheet="${esc(s.name)}">${esc(s.name)}</button>`).join('');const cells=new Map(s.cells.map(c=>[`${c.row},${c.column}`,c]));let rows='';for(let r=1;r<=s.headerRows;r++){rows+='<tr>';for(let c=1;c<=s.columns;c++){const m=s.merges.find(m=>r>=m.r1&&r<=m.r2&&c>=m.c1&&c<=m.c2);if(m&&(r!==m.r1||c!==m.c1))continue;rows+=`<th ${m?`rowspan="${m.r2-m.r1+1}" colspan="${m.c2-m.c1+1}"`:''}>${esc(cells.get(`${r},${c}`)?.value||'')}</th>`;}rows+='</tr>';}const body=s.rows.map((row,ri)=>'<tr>'+row.map((v,i)=>`<td class="${v==='未包含'?'missing':''}" data-result-field="${i}" data-result-row="${ri}" title="点击查看该工程的取值依据">${esc(v)}</td>`).join('')+'</tr>').join('');$('excel-wrap').innerHTML=`<table class="excel"><colgroup>${s.widths.map(w=>`<col style="width:${Math.max(90,w)}px">`).join('')}</colgroup><thead>${rows}</thead><tbody>${body}</tbody></table>${!s.rows.length?'<div class="empty"><h3>当前工程没有此类结果记录</h3></div>':''}`;const all=s.rows.flat();$('result-summary').textContent=`${s.rows.length} 条记录 · ${all.filter(v=>v!=='未包含').length-s.rows.length} 个指标已填 · ${all.filter(v=>v==='未包含').length} 个未包含`;$('result-footer').textContent=`${s.columns} 列 · 保留原模板 ${s.headerRows} 行表头 · 每个工程一行 · 点击单元格查看该工程依据`;}
function accumulate(output){
 const index=records.findIndex(r=>r.projectId===output.projectId);
 if(index<0)records.push(output);else records[index]=output;
 result=structuredClone(records[0]);const sheet=result.sheets[0];
 sheet.rows=[];sheet.rowFields=[];sheet.rowProjects=[];
 records.forEach((r,i)=>{
  const row=[...r.sheets[0].rows[0]];row[0]=i+1;sheet.rows.push(row);
  const fields=structuredClone(r.sheets[0].fields);
  fields.forEach(f=>{if(f.evidence)f.evidence.templateCell=f.column+(sheet.headerRows+i+1);(f.conflicts||[]).forEach(c=>c.templateCell=f.column+(sheet.headerRows+i+1));});
  sheet.rowFields.push(fields);sheet.rowProjects.push(r.projectName);
 });
 resultSheet=result.activeSheet;
 $('completed-projects').innerHTML=records.map((r,i)=>`<span class="project-record"><b>${i+1}. ${esc(r.projectName)}</b><small>${r.extraction.filled} 项有依据</small></span>`).join('');
 let scopes=$('project-scopes');if(!scopes){scopes=document.createElement('div');scopes.id='project-scopes';document.querySelector('.demo-scope').append(scopes);}
 scopes.innerHTML=records.map(r=>`<p><b>${esc(r.projectName)}</b>：${esc(r.extraction.scope)}<br>${esc(r.extraction.taxBasis)}</p>${r.extraction.issues.map(i=>`<p>${esc(i)}</p>`).join('')}`).join('');
 document.querySelector('[data-tab="report"]').hidden=false;
 reportId=output.projectId;if(costReports)renderCostReport();verificationProject=output.projectId;verificationFilter='全部';
 renderResult();return index>=0;
}
async function start(){
 if(!info||running)return;running=true;const token=++runId;lock(true);$('error').hidden=true;
 $('run-state').textContent='核验来源中';$('percent').textContent='…';$('progress-bar').style.width='0%';pipeline(4);
 $('event-text').textContent='正在核验真实来源并载入该工程结果';$('cancel').hidden=false;renderFiles();
 try{
  const output=await pacedRequest(api('/api/result',{...payload(),checkToken:info.checkToken}),token,[[0,0],[1000,12],[2600,29],[5200,44],[8200,68],[10200,87],[12000,97]],(percent,waiting)=>{
   $('percent').textContent=percent+'%';$('progress-bar').style.width=percent+'%';
   pipeline(Math.min(5,Math.floor(percent/17)));$('run-state').textContent='处理中';
   $('event-text').textContent=waiting?'等待来源核验结果':'流程展示 · 正在载入当前工程的预置结果';
  });if(token!==runId)return;
  currentOutput=output;const replaced=accumulate(output);pipeline(6);$('percent').textContent='完成';$('progress-bar').style.width='100%';$('run-state').textContent='已完成';
  $('event-text').textContent=`${output.projectName}已${replaced?'更新':'追加'} · ${output.extraction.filled} 项有依据 · 累计 ${records.length} 个工程`;
  $('export').disabled=exporting;renderFiles();tab('result');
 }catch(e){if(token!==runId)return;error(e);$('run-state').textContent='未完成';$('percent').textContent='—';}
 finally{if(token===runId){running=false;lock(false);$('start').textContent='重新抽取 →';$('cancel').hidden=true;}}
}
async function restore(){
 invalidate();lock(true);$('error').hidden=true;
 try{
  const d=await api('/api/defaults');
  ['folder','template','owl'].forEach(k=>$(k).value=d[k]);
  $('model-name').textContent=`离线模型：${d.model}`;$('model-name').title='配置的模型名称；本演示载入预置结果，不新增模型推理。';
 }catch(e){error(e);}finally{lock(false);}
}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));$('nav-task').onclick=()=>tab('files');$('nav-map').onclick=()=>tab('mapping');$('nav-results').onclick=()=>tab('result');$('restore').onclick=restore;$('inspect').onclick=inspect;$('start').onclick=start;
document.querySelectorAll('[data-pick]').forEach(b=>b.onclick=async()=>{lock(true);b.textContent='…';b.setAttribute('aria-busy','true');$('error').hidden=true;toast('请选择本机弹出的窗口；取消选择将保留原路径。');try{const r=await api('/api/pick',{kind:b.dataset.pick,current:$(b.dataset.pick).value.trim()});if(r.path){$(b.dataset.pick).value=r.path;invalidate();}}catch(e){error(e);}finally{b.removeAttribute('aria-busy');lock(false);}});
['folder','template','owl'].forEach(k=>$(k).addEventListener('input',invalidate));$('search-file').oninput=renderFiles;$('map-sheet').onchange=renderMapping;
$('file-types').onclick=e=>{const b=e.target.closest('[data-filter]');if(b){filter=b.dataset.filter;renderFiles();}};
$('map-body').onclick=e=>{const b=e.target.closest('[data-field]');if(b)detail(info.sheets.find(s=>s.name===$('map-sheet').value).fields[+b.dataset.field]);};
$('sheet-tabs').onclick=e=>{const b=e.target.closest('[data-sheet]');if(b){resultSheet=b.dataset.sheet;renderResult();}};
$('excel-wrap').onclick=e=>{const b=e.target.closest('[data-result-field]');if(b){const s=result.sheets.find(s=>s.name===resultSheet);const ri=+b.dataset.resultRow,ci=+b.dataset.resultField;detail(s.rowFields[ri][ci],s.rows[ri][ci],s.rowProjects[ri]);}};
$('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'继续':'暂停';$('run-state').textContent=paused?'已暂停':'处理中';};$('cancel').onclick=()=>{reset();renderFiles();toast('任务已取消，可以重新开始。');};
$('close-drawer').onclick=()=>$('drawer-backdrop').hidden=true;$('drawer-backdrop').onclick=e=>{if(e.target===$('drawer-backdrop'))$('drawer-backdrop').hidden=true;};document.addEventListener('keydown',e=>{if(e.key==='Escape')$('drawer-backdrop').hidden=true;});
$('export').onclick=async()=>{if(!result||exporting)return;const ids=records.map(r=>r.resultId),b=$('export');exporting=true;b.disabled=true;$('clear-results').disabled=true;b.textContent='正在生成…';try{const r=await api('/api/export',{resultIds:ids});const a=document.createElement('a');a.href=r.url;a.download=`工程指标抽取结果_${ids.length}个工程.xlsx`;document.body.append(a);a.click();a.remove();toast(`已导出本次选择的 ${ids.length} 个工程。`);}catch(e){error(e);}finally{exporting=false;b.disabled=!records.length;$('clear-results').disabled=running||!records.length;b.textContent='↓ 导出 Excel';}};
$('clear-results').onclick=()=>{
 records=[];result=null;currentOutput=null;invalidate();$('drawer-backdrop').hidden=true;
 reportId='';renderCostReport();verificationGeneration++;verificationData=[];verificationProject='';renderVerification();
 $('completed-projects').innerHTML='';$('sheet-tabs').innerHTML='';$('result-summary').textContent='完成抽取后显示填表结果';
 $('project-scopes')?.remove();
 $('excel-wrap').innerHTML='<div class="empty"><h3>等待生成结果</h3><p>每个工程一行，结果按提取顺序累计。</p></div>';
 $('result-footer').textContent='横向滚动查看完整模板字段';toast('已清空累计结果，请重新检查配置。');
};
pipeline();restore();

function appendEvidence(f){
 const e=f.evidence;
 if((e?.unit==='万元'||f.candidates?.length)&&['chuanshan','maoshan','xiuqing','peixian'].includes(detailProjectId))$('drawer-body').insertAdjacentHTML('afterbegin',`<button class="secondary" data-verify-jump="${esc(f.column)}" data-project="${esc(detailProjectId)}">查看数据核验 →</button>`);
 if(f.conflicts?.length)$('drawer-body').insertAdjacentHTML('afterbegin',`<div class="source-box"><h3>来源冲突 · 保留原值</h3>${f.conflicts.map(c=>`<p>${esc(c.reason)}</p><p>${esc(c.file)} · ${esc(c.location)}</p>`).join('')}</div>`);
 $('drawer-body').insertAdjacentHTML('afterbegin',e?`<div class="source-box"><h3>原始资料证据 · ${esc(e.route)}</h3><p><b>${esc(e.value)} ${esc(e.unit)}</b></p><h3>来源文件</h3><p>${detailProjectId&&e.unit==='万元'?`<button class="source-link" data-reveal-project="${esc(detailProjectId)}" data-reveal-column="${esc(f.column)}" title="打开所在文件夹并选中文件">${esc(e.file)} ↗</button>`:esc(e.file)}</p><h3>来源位置</h3><p>${esc(e.location)}</p><h3>原始值与换算</h3><p>${esc(e.rawValue)} ${esc(e.sourceUnit)}<br>${esc(e.conversion)}</p><h3>取值口径</h3><p>${esc(e.basis)}</p><h3>解析方式</h3><p>${esc(e.method)}</p><small>SHA256：${esc(e.sha256)}</small></div>`:`<div class="source-box"><h3>未回填原因</h3><p>${esc(f.missingReason||(f.column==='A'?'序号由当前累计顺序生成。':'本轮尚未取得来源证据。'))}</p></div>`);
}
let costReports=null,reportId='';
const money=v=>Number(v).toLocaleString('zh-CN',{minimumFractionDigits:4,maximumFractionDigits:4});
async function loadReports(){
 if(!records.length){renderCostReport();return;}
 try{if(!costReports)costReports=(await api('/api/cost-reports')).reports;renderCostReport();}
 catch(e){$('cost-report').textContent=e.message;}
}
function renderCostReport(){
 const available=(costReports||[]).filter(r=>records.some(p=>p.projectId===r.id));
 if(!available.length){$('report-tabs').innerHTML='';$('cost-report').innerHTML='<div class="empty">▤<h3>等待生成费用报告</h3><p>完成工程抽取后，显示该工程的费用报告。</p></div>';return;}
 const r=available.find(r=>r.id===reportId)||available[0];reportId=r.id;
 $('report-tabs').innerHTML=available.map(p=>`<button class="chip ${p.id===r.id?'selected':''}" data-report="${esc(p.id)}">${esc(p.name)}</button>`).join('');
 $('cost-report').innerHTML=`<div class="report-heading"><div class="eyebrow">PROJECT COST REVIEW</div><h2>${esc(r.name)} · 工程费用报告</h2><p>${esc(r.summary)}</p><span class="tag">${esc(r.stage)}</span></div>
 <div class="report-metrics"><div><small>静态投资 · 万元</small><strong>${r.totalApproved===false?"来源冲突":money(r.total)}</strong></div><div><small>动态投资 · 万元</small><strong>${r.dynamicApproved===false?"来源冲突":money(r.dynamic)}</strong></div><div><small>分析依据</small><strong class="report-stage">${esc(r.stage)}</strong><small>已整理费用指标</small></div></div>
 <p class="report-basis">${r.totalApproved===false?"静态投资尚未通过核验，暂不计算费用占比。":"费用占比以静态投资为分母。"}</p><h3>费用构成</h3><div class="cost-bars">${r.items.map(i=>`<div class="cost-row"><button class="source-link" data-cost-ref="${i.column}">${esc(i.label)}</button><div class="cost-track"><span style="width:${r.totalApproved===false?0:i.share}%"></span></div><b>${money(i.value)}</b><span>${r.totalApproved===false?"—":i.share.toFixed(2)+"%"}</span></div>`).join('')}</div>
 <div class="report-findings">${(r.documentFindings||[]).map((s,i)=>`<article><span class="report-number">${String(i+1).padStart(2,"0")}</span><div><h3>${esc(s.title)}</h3><p>${esc(s.text)}</p><small>${s.refs.map((e,j)=>`<button class="source-link" data-report-ref="${j}" data-report-finding="${i}" data-report-project="${r.id}">${esc(e.file.split(/[\\/]/).at(-1))} ↗</button> · ${esc(e.location)}`).join("<br>")}</small></div></article>`).join("")}${r.sections.map((s,i)=>`<article><span class="report-number">${String(i+1+(r.documentFindings||[]).length).padStart(2,"0")}</span><div><h3>${esc(s.title)}</h3><p>${esc(s.text)}</p></div></article>`).join('')}</div>
 <details class="report-evidence"><summary>金额依据 · ${r.sources.length} 项（点击文件名定位原文件）</summary><div class="report-source-table"><table><thead><tr><th>指标及关联分析</th><th>金额（万元）</th><th>来源与位置</th></tr></thead><tbody>${r.sources.map(e=>`<tr id="cost-source-${e.column}"><td>${esc(e.column)} · ${esc(e.label)}<small style="display:block;margin-top:8px">${esc(r.sections.filter(s=>s.columns.includes(e.column)).map(s=>s.title).join('；'))}</small></td><td>${money(e.value)}</td><td><button class="source-link" data-reveal-project="${r.id}" data-reveal-column="${e.column}" title="${esc(e.file)}">${esc(e.file.split(/[\\/]/).at(-1))} ↗</button><p>${esc(e.location)}</p><small>原值 ${esc(e.rawValue)} ${esc(e.sourceUnit)} · ${esc(e.conversion)}</small></td></tr>`).join('')}</tbody></table></div></details>
 `;
}
$('report-tabs').onclick=e=>{const b=e.target.closest('[data-report]');if(b){reportId=b.dataset.report;renderCostReport();}};
$('cost-report').onclick=e=>{const b=e.target.closest('[data-cost-ref]');if(b){document.querySelector('.report-evidence').open=true;const row=$('cost-source-'+b.dataset.costRef);row.scrollIntoView({behavior:'smooth',block:'center'});row.classList.add('source-highlight');setTimeout(()=>row.classList.remove('source-highlight'),2500);}};
document.addEventListener('click',async e=>{const b=e.target.closest('[data-reveal-project]');if(!b)return;b.disabled=true;try{await api('/api/reveal-source',{projectId:b.dataset.revealProject,column:b.dataset.revealColumn});toast('已请求打开来源文件夹并选中文件');}catch(e){error(e);toast(e.message);}finally{b.disabled=false;}});

document.addEventListener('click',async e=>{const b=e.target.closest('[data-report-ref]');if(!b)return;try{await api('/api/reveal-report-ref',{projectId:b.dataset.reportProject,findingIndex:+b.dataset.reportFinding,refIndex:+b.dataset.reportRef});toast('已请求打开报告来源文件夹');}catch(e){error(e);}});
