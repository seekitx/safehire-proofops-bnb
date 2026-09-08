// Read-only walkthrough. No wallet injection, payment replay or private workspace.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const out = path.join(root, '.data/submission-video');
fs.mkdirSync(out, { recursive: true });
const base = 'https://safehire.eyesonchain.xyz';
const caseUrl = process.env.SAFEHIRE_DEMO_CASE_URL || base + '/assets/submission-2026-09-08/index.html';
const scenes = [
  ['01-market', base + '/workspace', 'SafeHire: find a service, inspect its scope, and pay an exact signed price.', 'SafeHire helps people hire BNB Chain agents with evidence they can inspect. This is a live website walkthrough recorded after a real purchase. We will review the existing order, without repeating any payment.'],
  ['02-categories', base + '/workspace', 'Four category workflows. Current paid supply and execution depth are uneven.', 'The workspace separates grid calculations, liquidity positions, yield comparison, and lending risk. Each service explains what it does and what it does not do. Failed quotes remain unavailable. These calculators do not automatically trade or promise returns.'],
  ['03-quote', base + '/hire-live?skill_id=grid_plan&agent_token_id=269224', 'Signed 0.50 U quote. Caller-supplied example inputs. No wallet or transaction in this replay.', 'For this grid service, the provider signs a price of zero point five U. The owner previously supplied reference price seven hundred fifty, hypothetical capital one thousand dollars, five levels per side, and a two percent half span. These are calculation inputs, not current market facts.'],
  ['04-paid-order', caseUrl + '#journey', 'Actual mainnet order #56743: owner confirmed every wallet transaction.', 'Here are the actual mainnet transaction links for order fifty six thousand seven hundred forty three. The owner created the order inside SafeHire, bound the review policy, fixed the signed budget, approved the exact token amount, and funded escrow. The provider then submitted a result.'],
  ['05-result', caseUrl + '#result', 'Manifest, order, chain and contracts verified. Grid arithmetic independently recomputed.', 'SafeHire retrieved the original provider manifest and checked it against the on chain commitment. It also recomputed the task parameters, both sides, all ten prices, quantities, allocations, and the total budget. All arithmetic checks passed. This is a delivered calculation, not an executed trading strategy.'],
  ['06-followup', caseUrl + '#followup', 'Background order observation + Bark alert. Owner confirmed receiving the delivery notification.', 'The private workspace continued checking the order on the server. A new delivery triggered Bark, and the owner confirmed receiving the phone alert. Asked whether the result was worth the price, the owner said, I feel it is worth it. This is owner feedback transcribed by A I, not an independent review.'],
  ['07-boundaries', caseUrl + '#scope', 'Mainnet delivery submitted; final settlement pending. Review the evidence and try the product.', 'Mainnet settlement is still pending in the review window. A separate testnet order demonstrates completed settlement. Four category depth, independent supply, and valid unaided human comparisons remain development goals. SafeHire makes these boundaries explicit. The public site, source code, and raw evidence are available for review.'],
];
const q = p => p.replaceAll("'", "'\\''");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const concat=[]; const observations=[];
  for (const [name,url,caption,narration] of scenes) {
    fs.writeFileSync(path.join(out,name+'.txt'),narration);
    execFileSync('say',['-v','Samantha','-r','155','-f',path.join(out,name+'.txt'),'-o',path.join(out,name+'.aiff')]);
    const duration=Number(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','csv=p=0',path.join(out,name+'.aiff')],{encoding:'utf8'}).trim())+1.2;
    const context=await browser.newContext({viewport:{width:1440,height:960},recordVideo:{dir:out,size:{width:1440,height:960}},locale:'en-US'});
    const page=await context.newPage();
    await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
    if(name==='01-market'||name==='02-categories')await page.getByRole('heading',{name:'ChainHelix — Grid calculation',exact:true}).waitFor({timeout:30000});
    if(name==='03-quote')await page.getByRole('heading',{name:'ChainHelix — Grid calculation',exact:true}).waitFor({timeout:30000});
    await page.waitForTimeout(600);
    const start=Date.now();
    observations.push({scene:name,url,observed_at:new Date().toISOString(),text:await page.locator('body').innerText()});
    await page.screenshot({path:path.join(out,name+'.png')});
    if(name==='02-categories') {
      for(const label of ['收益比较','借贷风险','LP 仓位']) { await page.getByRole('button',{name:label,exact:true}).click(); await page.waitForTimeout(4500); }
    }
    if(name==='03-quote')await page.getByRole('group',{name:'网格计算参数（不会实际下单）'}).scrollIntoViewIfNeeded();
    await page.waitForTimeout(Math.max(1000,duration*1000-(Date.now()-start)));
    const video=page.video(); await context.close(); const file=await video.path();
    // Trim initial loading. Captions are editorial overlays outside the webpage.
    const total=Number(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','csv=p=0',file],{encoding:'utf8'}).trim());
    const capLines=caption.replace(/(.{1,77})(\s+|$)/g,'$1\n').trim();
    fs.writeFileSync(path.join(out,name+'-caption.txt'),capLines);
    const target=path.join(out,name+'.mp4');
    execFileSync('ffmpeg',['-y','-hide_banner','-loglevel','error','-ss',String(Math.max(0,total-duration)),'-i',file,'-i',path.join(out,name+'.aiff'),'-t',String(duration),'-vf',`pad=1440:1080:0:0:color=0x142c27,drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:textfile=${path.join(out,name+'-caption.txt')}:fontcolor=white:fontsize=25:x=36:y=984:line_spacing=8`,'-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-r','25','-c:a','aac','-ar','48000','-ac','2','-af','apad','-movflags','+faststart',target]);
    concat.push(`file '${q(target)}'`); console.log(name,'recorded',duration.toFixed(1),'seconds');
  }
  await browser.close();
  fs.writeFileSync(path.join(out,'concat.txt'),concat.join('\n'));
  fs.writeFileSync(path.join(out,'recording-observations.json'),JSON.stringify(observations,null,2));
  execFileSync('ffmpeg',['-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',path.join(out,'concat.txt'),'-c','copy','-movflags','+faststart',path.join(root,'apps/web/assets/submission-2026-09-08/safehire-demo.mp4')]);
  console.log('DEMO COMPLETE');
})().catch(e=>{console.error(e);process.exitCode=1});
