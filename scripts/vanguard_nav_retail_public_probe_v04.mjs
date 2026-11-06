/**
 * Public retail Vanguard NAV USD historical export probe, read-only.
 * Polish Vanguard individual-investor site for ISIN IE00BK5BQT80.
 * No age/category assertions, forced clicks, DOM manipulation, proxies,
 * credentials, broker actions, or hidden requests. Any UI block => NOT_RUN.
 */
import {chromium} from "playwright";
import {createHash} from "node:crypto";
import {readFileSync,mkdirSync} from "node:fs";
import path from "node:path";
const PAGE="https://www.pl.vanguard/inwestorzy-indywidualni/produkt/etf/akcje/9679/ftse-all-world-ucits-etf-usd-accumulating";
const ROOT="vanguard-nav-retail-evidence";
const result={source:"VANGUARD_OFFICIAL_RETAIL_PUBLIC",isin:"IE00BK5BQT80",
  origin:PAGE,download_status:"NOT_VERIFIED",historical_nav_36_months_validated:false,
  historical_first_usable_at_verified:false,executable_fill_price:false,
  research_backtest:"NOT_RUN",financial_operations:0,paper_events_created:0};
let browser;
function receipt(){console.log("VANGUARD_RETAIL_NAV_PROBE="+JSON.stringify(result));}
const official=(url)=>{try{const v=new URL(url);return v.protocol==="https:" &&
  ["www.pl.vanguard","pl.vanguard","www.vanguard.co.uk"].includes(v.hostname) &&
  !v.username && !v.password;}catch{return false;}};
try{
  browser=await chromium.launch({headless:true});
  const context=await browser.newContext({acceptDownloads:true,locale:"pl-PL"});
  const page=await context.newPage();
  const response=await page.goto(PAGE,{waitUntil:"domcontentloaded",timeout:50000});
  result.status=response?.status()??null;
  result.final_url=page.url();
  if(!official(page.url())||result.status!==200){
    result.download_status="OFFICIAL_RETAIL_SITE_UNAVAILABLE";
  }else{
    await page.waitForTimeout(3500);
    const choice=page.locator("#onetrust-reject-all-handler");
    const close=page.locator("#onetrust-close-btn-container button");
    result.cookie_action="NONE";
    if(await choice.isVisible({timeout:2000})){
      await choice.click({timeout:8000});result.cookie_action="REJECT_OPTIONAL_COOKIES";
    }else if(await close.isVisible({timeout:1200})){
      await close.click({timeout:7000});result.cookie_action="CLOSE_CONSENT_DIALOG";
    }
    await page.waitForTimeout(2200);
    const body=await page.locator("body").innerText({timeout:18000});
    result.page_has_isin=body.includes("IE00BK5BQT80");
    result.page_has_nav=body.includes("NAV");
    result.page_has_historical=/Historical Prices|Ceny historyczne|Ceny historyczne|Notowania historyczne/i.test(body);
    const allButtons=page.locator('button[data-cy="download-button"]');
    const buttonLabels=await allButtons.evaluateAll(els=>els.map(el=>({
      label:el.getAttribute("aria-label"), title:el.getAttribute("title"),
      text:(el.innerText||"").trim().slice(0,100),
      visible:!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length)
    })));
    result.all_button_labels=buttonLabels;
    const buttons=page.locator('button[data-cy="download-button"]:visible')
      .filter({hasText:/\b(?:prices|cen(?:y)?)\b/i});
    result.visible_download_buttons=await buttons.count();
    result.all_download_buttons=buttonLabels.length;
    if(!result.page_has_isin||!result.page_has_nav){
      result.download_status="RETAIL_PRODUCT_IDENTITY_NOT_VERIFIED";
    }else if(!result.visible_download_buttons){
      result.download_status="HISTORICAL_NAV_EXPORT_BUTTON_NOT_IDENTIFIED";
    }else{
      const button=buttons.first();
      const modalCandidates=page.locator('[role="dialog"],[aria-modal="true"],.onetrust-pc-dark-filter, #onetrust-banner-sdk');
      const blockers=await modalCandidates.evaluateAll(nodes=>nodes.filter(
        e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);return
          r.width>0&&r.height>0&&s.visibility!=="hidden"&&s.display!=="none";})
        .slice(0,6).map(e=>({tag:e.tagName,role:e.getAttribute("role"),
                           id:e.id,classes:String(e.className).slice(0,100),
                           short_text:(e.innerText||"").trim().slice(0,180)})));
      result.visible_modals=blockers;
      // Read-only classification of an nds-modal overlay. Do not dismiss
      // legal eligibility, investor-type or age declarations automatically.
      result.nds_modal_details=await page.locator("nds-modal").evaluateAll(els=>
        els.map(el=>{const r=el.getBoundingClientRect();return {
          visible:r.width>0&&r.height>0,
          text:(el.innerText||"").trim().slice(0,950),
          buttons:Array.from(el.querySelectorAll("button"))
            .slice(0,10).map(b=>({
               text:(b.innerText||"").trim().slice(0,90),
               aria:b.getAttribute("aria-label"),
               title:b.getAttribute("title")
            }))
        };}).filter(x=>x.visible).slice(0,3));

      const network=[];
      page.on("response",response=>{try{const url=new URL(response.url());
        if(official(response.url()) && /download|historical|price|export|nav/i.test(url.pathname)
          && network.length<10)network.push({host:url.host,path:url.pathname.slice(0,110),http:response.status()});
      }catch{}});
      // Only a normal visible click. Never force the click or dismiss
      // investor-category prompts by asserting an unverified identity.
      try{
        await button.scrollIntoViewIfNeeded({timeout:9000});
        const downloadPromise=page.waitForEvent("download",{timeout:15000});
        const click=await Promise.allSettled([
          downloadPromise,
          button.click({timeout:9000}),
        ]);
        result.click_status=click[1].status;
        result.public_network_receipts=network;
        if(click[0].status!=="fulfilled"||click[1].status!=="fulfilled"){
          result.download_status="RETAIL_EXPORT_DID_NOT_PRODUCE_FILE";
          result.diagnostic=click.map((x,i)=>x.status==="rejected"?
            (i===0?"download:":"click:")+String(x.reason?.message||x.reason).slice(0,1550)
            :null).filter(Boolean).join(" / ");
        }else{
          const dl=click[0].value;
          if(!official(dl.url()))throw Error("download from unverified origin");
          const filename=dl.suggestedFilename().replace(/[^A-Za-z0-9._-]/g,"_").slice(0,80);
          mkdirSync(ROOT,{recursive:true});
          const file=path.join(ROOT,filename||"nav-export.bin");
          await dl.saveAs(file);
          const bytes=readFileSync(file);
          if(!bytes.length||bytes.length>20_000_000)throw Error("unexpected export size");
          result.download_status="OFFICIAL_RETAIL_EXPORT_BYTES_UNVERIFIED";
          result.filename=filename;result.bytes=bytes.length;
          result.raw_sha256=createHash("sha256").update(bytes).digest("hex");
          result.magic_hex=bytes.subarray(0,40).toString("hex");
        }
      }catch(err){
        result.download_status="RETAIL_EXPORT_BLOCKED";
        result.diagnostic=String(err?.message||err).slice(0,450);
      }
    }
  }
}catch(err){
  result.download_status="RETAIL_BROWSER_OR_SOURCE_ERROR";
  result.diagnostic=String(err?.message||err).slice(0,450);
}finally{receipt();await browser?.close();}
