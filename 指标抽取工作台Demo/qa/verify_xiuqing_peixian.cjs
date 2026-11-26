const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1148,height:800}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:18864');await page.waitForFunction(()=>document.querySelector('#folder').value);
 assert.deepEqual(await page.locator('.tabs [data-tab]').allTextContents(),['文件清单','指标映射','模板结果','数据核验','费用报告']);
 await page.locator('[data-tab="verification"]').click();assert.ok((await page.locator('#verification-content').textContent()).includes('等待生成核验结果'));
 const defaults=await(await page.request.get('http://127.0.0.1:18864/api/defaults')).json();
 for(const id of ['xiuqing','peixian']){
  await page.locator('#folder').fill(defaults.projects.find(p=>p.id===id).folder);
  await page.locator('#inspect').click();await page.waitForFunction(()=>document.querySelector('#ready-text').textContent==='配置就绪');
  await page.locator('#start').click();await page.waitForFunction(()=>document.querySelector('#run-state').textContent==='已完成');
  await page.locator('[data-tab="verification"]').click();await page.locator('.verification-intro').waitFor();
  assert.equal(await page.locator('[data-verification-detail]').count(),id==="xiuqing"?34:35);
  assert.equal(await page.locator('.verification-status.verified').count(),id==='xiuqing'?30:33);
  await page.locator('[data-verification-detail="DT"]').click();assert.ok((await page.locator('#drawer-body').textContent()).includes('候选证据'));await page.locator('#close-drawer').click();
  await page.locator('.verification-filters [data-verification-filter="来源冲突"]').click();assert.ok((await page.locator('.verification-table').textContent()).includes(id==='xiuqing'?'10080.54':'没有指标'));
  await page.locator('.verification-filters [data-verification-filter="全部"]').click();
  assert.equal(await page.locator('.modality-grid article').count(),6);
 }
 assert.equal(await page.locator('[data-verification-project]').count(),2);
 await page.locator('[data-verification-project="xiuqing"]').click();assert.ok((await page.locator('.verification-intro').textContent()).includes('扬州秀清'));
 await page.screenshot({path:__dirname+'/verification-xiuqing-peixian.png',fullPage:true});
 await page.locator('[data-tab="report"]').click();await page.locator('.report-heading').waitFor();assert.equal(await page.locator('[data-report]').count(),2);await page.locator('[data-report="xiuqing"]').click();assert.ok((await page.locator('#cost-report').textContent()).includes('10080.54'));await page.locator('[data-report="peixian"]').click();assert.ok((await page.locator('#cost-report').textContent()).includes('6471'));
 await page.locator('[data-tab="result"]').click();assert.equal(await page.locator('[data-result-row="0"][data-result-field="123"]').textContent(),'未包含');assert.equal(await page.locator('[data-result-row="0"][data-result-field="115"]').textContent(),'未包含');const download=page.waitForEvent('download',{timeout:180000});await page.locator('#export').click();await(await download).saveAs(__dirname+'/../outputs/秀清沛县候选核验结果.xlsx');await page.locator('[data-result-row="0"][data-result-field="123"]').click();
 await page.locator('[data-verify-jump]').click();await page.locator('#drawer-backdrop:not([hidden])').waitFor();assert.ok((await page.locator('#drawer-body').textContent()).includes('回填决定'));await page.locator('#close-drawer').click();
 await page.locator('#clear-results').click();assert.ok((await page.locator('#verification-content').textContent()).includes('等待生成核验结果'));
 assert.equal(await page.locator('[data-verification-project]').count(),0);
 await page.reload();await page.locator('[data-tab="verification"]').click();assert.ok((await page.locator('#verification-content').textContent()).includes('等待生成核验结果'));
 assert.deepEqual(errors,[]);console.log('PASS: two projects,69 decisions, filters, evidence, modalities, report, cell jump, clear and reload.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
