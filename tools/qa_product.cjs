// Disposable preview instance only. Captures actual page layouts and report download.
const {chromium}=require(process.argv[2]);const fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{const auth=JSON.parse(fs.readFileSync(process.argv[3],'utf8').replace(/^\uFEFF/,''));const out=path.resolve('docs/evidence/phase4');fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{const page=await browser.newPage({baseURL:'http://127.0.0.1:5173',viewport:{width:1366,height:768}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('/',{waitUntil:'domcontentloaded'});await page.getByLabel('Username').fill('admin');await page.getByLabel('Password').fill(auth.password);await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('button',{name:'Sign out'}).waitFor();
const results=[];
for(const [width,height] of [[1366,768],[1920,1080],[820,1180]]){await page.setViewportSize({width,height});for(const [name,url] of [['dashboard','/'],['cameras','/cameras'],['violations','/violations'],['upload','/upload'],['settings','/settings'],['logs','/logs'],['help','/help']]){await page.goto(url,{waitUntil:'domcontentloaded'});await page.getByRole('button',{name:'Sign out'}).waitFor();await page.waitForTimeout(700);const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));await page.screenshot({path:path.join(out,`${name}-${width}.png`)});results.push({page:name,width,height,overflow:overflow.scroll>width,scroll_width:overflow.scroll});}}
await page.setViewportSize({width:1366,height:768});
await page.goto('/upload',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>{const input=document.querySelector('input[type=file]');return input&&!input.disabled;});
await page.locator('input[type=file]').setInputFiles(path.join(path.dirname(process.argv[3]),'assets/helmet_vest.jpg'));
await page.getByAltText('Annotated PPE result').waitFor({timeout:20000});
await page.screenshot({path:path.join(out,'upload-observation.png')});
const analytics=await(await page.request.get('/api/stats/analytics')).json();
assert.ok(analytics.compliance_trend.some(row=>row.frames_analyzed>0));
fs.writeFileSync(path.join(out,'observed-analytics.json'),JSON.stringify({command:'tools/qa_product.cjs: real image upload followed by GET /api/stats/analytics',data:analytics},null,2));
await page.goto('/',{waitUntil:'domcontentloaded'});await page.getByRole('heading',{name:'Historical analytics'}).waitFor();
await page.getByRole('heading',{name:'Historical analytics'}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'observed-analytics.png')});
await page.goto('/settings',{waitUntil:'domcontentloaded'});await page.getByLabel('Detection frame interval').fill('4');await page.getByRole('button',{name:/Save Changes/i}).click();await page.getByText(/Saved successfully/).waitFor();
const saved=await(await page.request.get('/api/settings/alerts')).json();assert.equal(saved.frame_skip,4);
assert.equal(await page.getByRole('button',{name:'Enable live delivery'}).isDisabled(),true);
const session=await(await page.request.get('/api/auth/session')).json();const blocked=await page.request.post('/api/settings/alerts/delivery',{headers:{'X-CSRF-Token':session.csrf_token},data:{mode:'live',confirmation:'ENABLE LIVE ALERTS'}});assert.equal(blocked.status(),409);
await page.screenshot({path:path.join(out,'settings-preview.png')});
await page.goto('/violations',{waitUntil:'domcontentloaded'});await page.getByLabel('Review status').selectOption('escalated');await page.getByRole('button',{name:'APPLY FILTERS'}).click();await page.waitForTimeout(700);
const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export PDF Report'}).click();const file=await download;await file.saveAs(path.join(out,'filtered-report.pdf'));assert.equal(fs.readFileSync(path.join(out,'filtered-report.pdf')).subarray(0,5).toString(),'%PDF-');
await page.screenshot({path:path.join(out,'filtered-report.png')});
const current=await(await page.request.get('/api/settings/alerts')).json();await page.request.put('/api/settings/alerts',{headers:{'X-CSRF-Token':session.csrf_token},data:{...current,frame_skip:3}});
fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify({command:'node tools/qa_product.cjs <Playwright-directory> <temporary-auth.json>',layouts:results,frame_skip_saved:'pass',preview_live_block:'pass',pdf_download:'pass',page_errors:errors},null,2));assert.ok(results.every(x=>!x.overflow),JSON.stringify(results.filter(x=>x.overflow)));assert.deepEqual(errors,[]);console.log('PASS: all page layouts, persisted frame interval, preview restriction and actual PDF download.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
