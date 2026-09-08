// Re-record real public pages; preserve the existing narration and caption timing.
// No wallet injection, payments, private workspaces or fabricated API responses.
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');const out=path.join(root,'.data/english-refresh/video');fs.mkdirSync(out,{recursive:true});
const base=process.env.SAFEHIRE_DEMO_BASE||'https://safehire.eyesonchain.xyz';
const pub=path.join(root,'apps/web/assets/submission-2026-09-08');
const timings=JSON.parse(fs.readFileSync(path.join(pub,'redub-manifest.json'))).scenes;
const urls=['/workspace','/workspace','/hire-live?skill_id=grid_plan&agent_token_id=269224','/assets/submission-2026-09-08/index.html#journey','/assets/submission-2026-09-08/index.html#result','/assets/submission-2026-09-08/index.html#followup','/assets/submission-2026-09-08/index.html#scope'];
const probe=p=>Number(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','csv=p=0',p],{encoding:'utf8'}));
(async()=>{const browser=await chromium.launch({headless:true});const parts=[],observations=[];
for(let i=0;i<timings.length;i++){const scene=timings[i],duration=scene.scene_seconds;const context=await browser.newContext({viewport:{width:1440,height:960},recordVideo:{dir:out,size:{width:1440,height:960}},locale:'en-US',reducedMotion:'reduce'});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base+urls[i],{waitUntil:'domcontentloaded',timeout:45000});
if(i<2)await page.locator('.service-card').first().waitFor({timeout:45000});
if(i===2){await page.getByRole('heading',{name:'ChainHelix — Grid calculation',exact:true}).waitFor({timeout:45000});await page.locator('.brief-card').scrollIntoViewIfNeeded();}
if(i===1)await page.locator('#services-section').scrollIntoViewIfNeeded();
await page.waitForTimeout(500);const initialText=await page.locator('body').innerText();if(/\p{Script=Han}/u.test(initialText))throw new Error('Non-English content in scene '+scene.scene);if(errors.length)throw new Error(errors.join('; '));
const started=Date.now();const observed={scene:scene.scene,url:page.url(),recorded_at:new Date().toISOString(),duration_seconds:duration,visible_text:initialText,category_states:[]};
if(i===0){await page.waitForTimeout(4200);await page.locator('#services-section').scrollIntoViewIfNeeded();}
if(i===1){for(const label of ['Grid calculation','LP positions','Yield comparison','Lending risk']){await page.getByRole('button',{name:label,exact:true}).click();const text=await page.locator('#services-section').innerText();if(/\p{Script=Han}/u.test(text))throw new Error('Non-English category text');observed.category_states.push({label,text});await page.waitForTimeout(Math.min(3500,duration*1000/5));}}
if(i===2){await page.waitForTimeout(6500);await page.getByRole('group',{name:'Grid calculation inputs (no orders placed)',exact:true}).scrollIntoViewIfNeeded();}
await page.waitForTimeout(Math.max(100,duration*1000-(Date.now()-started)));await page.screenshot({path:path.join(out,scene.scene+'.png')});const video=page.video();await context.close();const raw=await video.path();const target=path.join(out,scene.scene+'.mp4');const total=probe(raw);
execFileSync('ffmpeg',['-y','-hide_banner','-loglevel','error','-ss',String(Math.max(0,total-duration)),'-i',raw,'-t',String(duration),'-vf','pad=1440:1080:0:0:color=0x142c27','-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r','25',target]);parts.push(target);observations.push(observed);console.log(scene.scene+': real English page recorded');}
await browser.close();const concat=path.join(out,'concat.txt');fs.writeFileSync(concat,parts.map(p=>`file '${p}'`).join('\n'));const srt=path.join(pub,'safehire-demo.en.srt');const style='FontName=Arial,FontSize=12,PrimaryColour=&H00FFFFFF,OutlineColour=&H00272C14,Outline=0.7,Shadow=0,Alignment=2,MarginV=8,MarginL=20,MarginR=20';const final=path.join(out,'safehire-demo.mp4');
execFileSync('ffmpeg',['-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',concat,'-i',path.join(pub,'safehire-demo.mp4'),'-map','0:v:0','-map','1:a:0','-vf',`subtitles=${srt}:force_style='${style}'`,'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r','25','-c:a','copy','-movflags','+faststart',final]);fs.writeFileSync(path.join(out,'recording-observations.json'),JSON.stringify(observations,null,2));console.log('VISUAL REFRESH COMPLETE',probe(final));})().catch(e=>{console.error(e);process.exitCode=1});
