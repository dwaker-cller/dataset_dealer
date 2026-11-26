const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1148,height:800}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:18864');
  await page.waitForFunction(()=>document.querySelector('#folder').value);
  const defaults=await(await page.request.get('http://127.0.0.1:18864/api/defaults')).json();
  await page.locator('#folder').fill(defaults.projects.find(p=>p.id==='puti').folder);
  await page.locator('#inspect').click();
  await page.waitForFunction(()=>document.querySelector('#ready-text').textContent==='配置就绪');
  await page.locator('#start').click();
  await page.waitForFunction(()=>document.querySelector('#run-state').textContent==='已完成');
  await page.locator('[data-tab="verification"]').click();
  await page.locator('.verification-intro').waitFor();
  assert.equal(await page.locator('[data-verification-detail]').count(),24);
  assert.equal(await page.locator('.verification-status.verified').count(),20);
  assert.equal(await page.locator('.verification-status.pending').count(),4);
  await page.locator('[data-tab="report"]').click();
  await page.locator('.report-heading').waitFor();
  assert.ok((await page.locator('#cost-report').textContent()).includes('5375.37'));
  await page.locator('[data-tab="result"]').click();
  const download=page.waitForEvent('download',{timeout:180000});
  await page.locator('#export').click();
  await(await download).saveAs(__dirname+'/../outputs/最新成果同步验证.xlsx');
  assert.deepEqual(errors,[]);
  console.log('PASS: latest Puti UI, 24 candidates, 20 approved, 4 pending, report, Excel download, no JS errors');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
