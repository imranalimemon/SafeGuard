// Local disposable-instance QA. No physical cameras or live transports.
const {chromium}=require(process.argv[2]);
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const auth=JSON.parse(fs.readFileSync(process.argv[3],'utf8').replace(/^\uFEFF/,''));
 const out=path.resolve('docs/evidence/phase2'); fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try {
  const page=await browser.newPage({baseURL:'http://127.0.0.1:5173',viewport:{width:1366,height:768}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:5173',{waitUntil:'domcontentloaded'});
  await page.getByLabel('Username').fill('admin'); await page.getByLabel('Password').fill(auth.password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click(); await page.getByRole('button',{name:'Sign out'}).waitFor();
  const session=await (await page.request.get('/api/auth/session')).json();
  const headers={'X-CSRF-Token':session.csrf_token};
  const suffix=Date.now();
  const good=await (await page.request.post('/api/cameras',{headers,data:{name:'QA replay '+suffix,source_type:'ip',url:'http://127.0.0.1:8001/camera-a.mjpg'}})).json();
  const bad=await (await page.request.post('/api/cameras',{headers,data:{name:'QA unavailable '+suffix,source_type:'rtsp',url:'rtsp://127.0.0.1:1/x'}})).json();
  assert.ok(good.id); assert.ok(bad.id);
  await page.reload({waitUntil:'domcontentloaded'});
  await page.locator('select').selectOption(String(good.id));
  await page.getByAltText('Live feed').waitFor({timeout:20000});
  await page.waitForTimeout(1200);
  await page.screenshot({path:path.join(out,'stream.png')});
  await page.locator('select').selectOption(String(bad.id));
  await page.getByText('Camera not available; reconnecting.',{exact:true}).waitFor({timeout:20000});
  assert.equal(await page.getByAltText('Live feed').count(),0);
  await page.screenshot({path:path.join(out,'reconnecting.png')});
  await page.locator('select').selectOption(String(good.id));
  await page.getByAltText('Live feed').waitFor({timeout:20000});
  await page.getByRole('button',{name:/STOP/}).click();
  await page.goto('http://127.0.0.1:5173/logs',{waitUntil:'domcontentloaded'});
  await page.getByRole('button',{name:'Refresh logs'}).waitFor();
  const logText=await page.getByLabel('Operational log lines').innerText();
  assert.match(logText,/Backend started/); assert.match(logText,/reconnect/);
  await page.screenshot({path:path.join(out,'logs.png')});
  await page.goto('http://127.0.0.1:5173/help',{waitUntil:'domcontentloaded'});
  await page.getByRole('heading',{name:'Safety Protocols and Help'}).waitFor();
  await page.screenshot({path:path.join(out,'help.png')});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify({command:'node tools/qa_reliability.cjs <Playwright directory> <temporary auth.json>',annotated_video_stream:'pass',camera_switch_to_failure:'pass',reconnect_status_clears_frame:'pass',switch_back_recovers:'pass',real_logs:'pass',help:'pass',page_errors:errors},null,2));
  console.log('PASS: stream, failure/reconnect, camera switching, real log page and help.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});