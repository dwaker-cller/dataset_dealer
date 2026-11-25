let verificationData=[],verificationProject='',verificationFilter='全部',verificationGeneration=0;
async function loadVerification(column){
 const generation=++verificationGeneration;
 if(!records.length){verificationData=[];renderVerification();return;}
 $('verification-content').innerHTML='<div class="empty">正在读取核验记录…</div>';
 try{const data=await api('/api/verification');if(generation!==verificationGeneration)return;verificationData=data.projects;renderVerification();if(column)verificationDetail(column);}
 catch(e){if(generation===verificationGeneration)$('verification-content').textContent=e.message;}
}
function renderVerification(){
 const available=verificationData.filter(p=>records.some(r=>r.projectId===p.id));
 const p=available.find(p=>p.id===verificationProject)||available[0];
 if(p)verificationProject=p.id;
 $('verification-projects').innerHTML=available.map(p=>`<button class="chip ${p.id===verificationProject?'selected':''}" data-verification-project="${p.id}">${esc(p.name)}</button>`).join('');
 if(!p){$('verification-content').innerHTML=`<div class="empty">▤<h3>${records.length?'当前工程尚未整理核验记录':'等待生成核验结果'}</h3><p>完成已整理工程的抽取后，显示指标核验与模态处理。</p></div>`;return;}
 const items=p.items.filter(i=>verificationFilter==='全部'||i.status===verificationFilter);
 $('verification-content').innerHTML=`<div class="verification-intro"><div class="eyebrow">DATA VERIFICATION</div><h2>${esc(p.name)} · 数据核验</h2><p>本次纳入核验 ${p.items.length} 项费用指标。完全没有依据的指标在模板中显示“未包含”，不计入这里。</p><p class="muted">程序 / OCR 提供候选，结合上下文比对后决定回填；待核验与来源冲突不填入模板。</p></div>
 <div class="verification-body"><h3>指标核验</h3><div class="verification-counts">${Object.entries(p.counts).map(([s,n])=>`<button class="verification-count ${s==='已核验'?'verified':s==='来源冲突'?'conflict':'pending'}" data-verification-filter="${s}"><span>${s}</span><strong>${n}<small> 项</small></strong></button>`).join('')}</div>
 <div class="chips verification-filters">${['全部','已核验','待核验','来源冲突'].map(s=>`<button class="chip ${verificationFilter===s?'selected':''}" data-verification-filter="${s}">${s}</button>`).join('')}</div>
 <div class="verification-table"><table><thead><tr><th>费用指标</th><th>模板当前值（万元）</th><th>候选金额（万元）</th><th>核验状态</th><th>核验说明</th><th>依据</th></tr></thead><tbody>${items.map(i=>`<tr id="verification-${i.column}"><td><b>${i.column}</b> ${esc(i.label.split(' / ').slice(1).join(' / '))}</td><td>${esc(records.find(r=>r.projectId===p.id)?.sheets[0].fields.find(f=>f.column===i.column)?.evidence?.value??'未包含')}</td><td>${esc((i.candidates||[]).map(c=>c.value).join(" / "))}</td><td><span class="verification-status ${i.status==='已核验'?'verified':i.status==='来源冲突'?'conflict':'pending'}">${i.status}</span></td><td>${esc(i.reason)}</td><td><button class="source-link" data-verification-detail="${i.column}">查看详情 ↗</button></td></tr>`).join('')||'<tr><td colspan="6">当前筛选下没有指标。</td></tr>'}</tbody></table></div>
 <p class="verification-note">${esc(p.note)}</p><h3>模态处理</h3><p class="muted">目录数量包含解压后的资料，按文件计数。下方记录原生解析、OCR与失败情况；解析完成不等于所有内容均能准确识别。</p>
 <div class="modality-grid">${p.modalities.map(m=>`<article><div class="modality-title"><h4>${esc(m.name)}</h4><span>${m.count} 份</span></div><span class="tag">${esc(m.state)}</span><p>${esc(m.detail)}</p><small>${esc(m.limit)}</small></article>`).join('')}</div><details class="demo-scope"><summary>逐文件处理明细 · ${p.documents?.length||0} 份</summary>${(p.documents||[]).map(d=>`<p>${esc(d.file.split(/[\\/]/).at(-1))} · ${esc(d.status)} · ${esc(d.issues.join("、"))}</p>`).join("")}</details></div>`;
}
function verificationDetail(col){
 const p=verificationData.find(p=>p.id===verificationProject),i=p?.items.find(i=>i.column===col);if(!i)return;
 const e=i.evidence;$('drawer-title').textContent=`${i.column} · ${i.label.split(' / ').at(-1)}`;
 $('drawer-body').innerHTML=`<p>${esc(p.name)} · <b>${i.status}</b></p><h3>比对结论与回填决定</h3><p>${esc(i.reason)}</p><p>${i.status==='已核验'?'通过口径比对，允许回填。':'暂不回填，模板保持“未包含”。'}</p><h3>候选证据</h3>${(i.candidates||[]).map((c,index)=>`<div class="source-box"><h3>${esc(c.value)} ${esc(c.unit)} · ${esc(c.disposition)}</h3><p>${esc(c.reason)}</p><button class="source-link" data-candidate-index="${index}" data-candidate-column="${col}" data-candidate-project="${p.id}">${esc(c.file)} ↗</button><p>${esc(c.location)}</p><p>原值 ${esc(c.rawValue)} ${esc(c.sourceUnit)} · ${esc(c.conversion)}</p></div>`).join('')}<h3>判断记录</h3><p>${esc(i.checkedAt)} · 结合原始上下文判断工程、阶段、费用范围及单位。</p><ul>${i.checks.map(c=>`<li>${esc(c)}</li>`).join('')}</ul><h3>费用口径</h3><p>${esc(i.basis)}</p>`;
 $('drawer-backdrop').hidden=false;$('close-drawer').focus();
}
$('verification-projects').onclick=e=>{const b=e.target.closest('[data-verification-project]');if(b){verificationProject=b.dataset.verificationProject;verificationFilter='全部';renderVerification();}};
$('verification-content').onclick=e=>{const f=e.target.closest('[data-verification-filter]'),d=e.target.closest('[data-verification-detail]');if(f){verificationFilter=f.dataset.verificationFilter;renderVerification();}if(d)verificationDetail(d.dataset.verificationDetail);};
document.addEventListener('click',e=>{const b=e.target.closest('[data-verify-jump]');if(!b)return;verificationProject=b.dataset.project;verificationFilter='全部';$('drawer-backdrop').hidden=true;tab('verification',b.dataset.verifyJump);});

document.addEventListener('click',async e=>{const b=e.target.closest('[data-candidate-index]');if(!b)return;try{await api('/api/reveal-candidate',{projectId:b.dataset.candidateProject,column:b.dataset.candidateColumn,index:+b.dataset.candidateIndex});toast('已请求打开候选来源文件夹');}catch(e){error(e);}});
