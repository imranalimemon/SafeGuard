// Adapted final pass: authenticated disposable preview instance.
const {chromium}=require(process.argv[2]);
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=path.dirname(process.argv[3]), shots='I:/AntiGRavity/SafeGuard/docs/screenshots';
const results=[],telemetry=[];let area='startup';
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const context=await browser.newContext({baseURL:'http://127.0.0.1:5173',viewport:{width:1540,height:1100},acceptDownloads:true,timezoneId:'Asia/Karachi'});
 await context.route(/https:\/\/(api|web)\.whatsapp\.com\//,route=>route.abort());
 const page=await context.newPage();page.setDefaultTimeout(12000);
 const ws=[];page.on('websocket',s=>{if(!s.url().includes('/ws/stream/'))return;const v={url:s.url(),closed:false,frames:0};ws.push(v);s.on('close',()=>v.closed=true);s.on('framereceived',()=>v.frames++);});
 page.on('pageerror',e=>telemetry.push({area,type:'pageerror',message:e.message}));
 page.on('console',m=>{if(m.type()==='error')telemetry.push({area,type:'console',message:m.text()})});
 page.on('requestfailed',r=>telemetry.push({area,type:'network',url:r.url(),error:r.failure()?.errorText}));
 page.on('response',r=>{if(r.status()>=400)telemetry.push({area,type:'http',url:r.url(),status:r.status()})});
 async function run(name,fn){area=name;let detail;try{detail=await fn();await page.waitForTimeout(350);const file='master-qa-'+name+'.png';await page.screenshot({path:path.join(shots,file),fullPage:true});results.push({area:name,result:'PASS',detail,evidence:'docs/screenshots/'+file});console.log('PASS',name);}catch(e){const file='master-qa-'+name+'-before-fix.png';await page.screenshot({path:path.join(shots,file),fullPage:true}).catch(()=>{});results.push({area:name,result:'FAIL',error:e.message,evidence:'docs/screenshots/'+file});console.log('FAIL',name,e.message);}}
 async function go(route){await page.locator(`a[href="${route}"]`).first().click();await page.waitForTimeout(650);}
 const card=name=>page.locator('div.glass-panel').filter({has:page.getByRole('heading',{name,exact:true})}).first();
 async function create(name,url){await page.getByRole('button',{name:/Add Camera/}).first().click();await page.getByPlaceholder('e.g. CAM-01: Main Entrance').fill(name);await page.locator('select').first().selectOption('ip');await page.getByPlaceholder('rtsp://user:pass@192.168.1.x:554/stream1').fill(url);const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/cameras');await page.getByRole('button',{name:'Apply Config',exact:true}).click();const r=await response;assert.equal(r.status(),201);const data=await r.json();await page.getByRole('heading',{name,exact:true}).waitFor();return data;}


 try{
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await page.getByLabel('Username').fill('admin');
 const auth=JSON.parse(fs.readFileSync(process.argv[3],'utf8').replace(/^\uFEFF/,''));
 await page.getByLabel('Password').fill(auth.password);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.getByRole('button',{name:'Sign out'}).waitFor();
 const session=await(await page.request.get('/api/auth/session')).json();
 for(const method of ['post','put','patch','delete']){
   const original=page.request[method].bind(page.request);
   page.request[method]=(url,options={})=>original(url,{...options,headers:{...options.headers,'X-CSRF-Token':session.csrf_token}});
 }

 await page.goto('/cameras',{waitUntil:'domcontentloaded'});await page.waitForTimeout(800);const existing=await(await page.request.get('/api/cameras')).json();let c=existing.find(c=>c.name==='QA protected camera');if(c)await page.request.put('/api/cameras/'+c.id,{data:{password:'dummy-qa-password'}});else c=await(await page.request.post('/api/cameras',{data:{name:'QA protected camera',source_type:'ip',url:'http://127.0.0.1:8001/camera-a.mjpg',username:'master-qa-user',password:'dummy-qa-password',enabled:false}})).json();await page.reload({waitUntil:'domcontentloaded'});await page.waitForTimeout(500);
 await run('58-camera-password-preserved',async()=>{await card(c.name).getByRole('button',{name:'Edit',exact:true}).click();await page.getByPlaceholder('Optional camera location').fill('Updated location');await page.getByRole('button',{name:'Apply Config',exact:true}).click();await page.waitForTimeout(400);const after=await(await page.request.get('/api/cameras/'+c.id)).json();assert.equal(after.has_credentials,true);assert.equal(after.password,undefined);assert.equal(after.username,undefined);});
 await run('59-camera-delete-error-visible',async()=>{await page.route('**/api/cameras/'+c.id,r=>r.request().method()==='DELETE'?r.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'Synthetic delete failure'})}):r.continue());page.once('dialog',d=>d.accept());await card(c.name).getByRole('button',{name:'Delete',exact:true}).click();await page.getByText('Synthetic delete failure',{exact:true}).waitFor({timeout:2500});});await page.unroute('**/api/cameras/'+c.id);
 await run('60-camera-validation-does-not-crash',async()=>{await page.getByRole('button',{name:/Add Camera/}).first().click();await page.getByPlaceholder('e.g. CAM-01: Main Entrance').fill('x'.repeat(121));const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/cameras');await page.getByRole('button',{name:'Apply Config',exact:true}).click();assert.equal((await pending).status(),422);await page.getByText(/at most 120/).waitFor({timeout:2500});assert.equal(await page.getByRole('heading',{name:'Camera Management',exact:true}).count(),1);});await page.goto('/cameras',{waitUntil:'domcontentloaded'});await page.waitForTimeout(600);
 await run('61-discovery-selection-ui-fixture',async()=>{await page.route('**/api/cameras/auto-detect*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({local:[{index:60,width:640,height:480,backend:'QA fixture only'}],onvif:[]})}));await page.getByRole('button',{name:/Auto-Detect/}).click();await page.getByText('Webcam 60',{exact:true}).waitFor();const add=page.getByRole('button',{name:/Add Selected/});assert.equal(await add.isDisabled(),true);await page.getByRole('checkbox').check();assert.equal(await add.isDisabled(),false);await add.click();await page.getByRole('heading',{name:'Webcam 60',exact:true}).waitFor();page.once('dialog',d=>d.accept());await card('Webcam 60').getByRole('button',{name:'Delete',exact:true}).click();await page.getByRole('heading',{name:'Webcam 60',exact:true}).waitFor({state:'hidden'});return 'Discovery UI and real config create/delete tested with synthetic discovery response; no hardware opened';});
 await run('62-global-navigation',async()=>{for(const [name,route] of [['Live View','/'],['Analysis','/upload'],['Violations','/violations'],['Settings','/settings']]){await page.locator('header').getByRole('link',{name,exact:true}).click();assert.equal(new URL(page.url()).pathname,route);await page.waitForTimeout(250);}return 'Header and sidebar routes work';});
 }finally{fs.writeFileSync(path.join(root,'phase-e2-results.json'),JSON.stringify({results,telemetry},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
