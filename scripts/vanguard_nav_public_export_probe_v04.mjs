/**
 * Probe the official, publicly visible Vanguard FTSE All-World USD
 * accumulating NAV historical-price export using a headless browser.
 * No authentication, cookies from users, circumvention, payments, or
 * brokerage interaction. Never trust a third-party NAV dataset here.
 *
 * The output is EVIDENCE, not a validated total-return series or fill price.
 */
import { chromium } from "playwright";
import { createHash } from "node:crypto";
import { readFileSync, mkdirSync } from "node:fs";
import path from "node:path";

const PAGE="https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits";
const ROOT="vanguard-nav-public-probe";
const result={
  origin:PAGE,
  isin:"IE00BK5BQT80",
  source:"VANGUARD_OFFICIAL_PUBLIC_PRODUCT",
  download_status:"NOT_VERIFIED",
  usable_monthly_NAV_series:false,
  point_in_time_certified:false,
  financial_operations:0,
  paper_events_created:0,
};
const done=()=>console.log("VANGUARD_OFFICIAL_EXPORT_PROBE="+JSON.stringify(result));
let browser;
try {
  browser=await chromium.launch({headless:true});
  const context=await browser.newContext({acceptDownloads:true,locale:"en-GB"});
  const page=await context.newPage();
  const resp=await page.goto(PAGE,{waitUntil:"domcontentloaded",timeout:65000});
  result.page_status=resp?.status()??null;
  await page.waitForTimeout(12000);
  const body=await page.locator("body").innerText({timeout:20000});
  result.public_page_has_ISIN=body.includes("IE00BK5BQT80");
  result.public_page_has_NAV=body.includes("NAV");
  result.public_page_has_download_text=/Download\s+[\d,]+\s+prices/i.test(body);
  if(!result.public_page_has_ISIN || !result.public_page_has_NAV){
    result.download_status="PUBLIC_PAGE_IDENTITY_NOT_VERIFIED";
    done();
  }else{
    const terms=page.getByText(/Download\s+[\d,]+\s+prices/i);
    result.visible_download_controls=await terms.count();
    if(result.visible_download_controls===0){
      result.download_status="EXPORT_CONTROL_NOT_VISIBLE";
      done();
    }else{
      // The visible label is a nested SPAN: interact with the actual BUTTON.
      const button=terms.first().locator("xpath=..");
      await button.scrollIntoViewIfNeeded({timeout:15000});
      const observedNetwork=[];
      page.on("response",(res)=>{
        const uri=res.url();
        if(/price|csv|export|historical|nav/i.test(uri)){
          try {
            const host=new URL(uri).hostname;
            if((host==="www.vanguard.co.uk"||host.endsWith(".vanguard.com"))
                  && observedNetwork.length<14){
              observedNetwork.push({host,path:new URL(uri).pathname.slice(0,140),
                                    http:res.status()});
            }
          }catch{}
        }
      });
      result.control_element=await button.evaluate(el=>({
        tag:el.tagName,
        role:el.getAttribute("role"),
        disabled:el.getAttribute("disabled"),
        class_excerpt:(el.className||"").toString().slice(0,120),
        parent_tag:el.parentElement?.tagName??null,
        outer_html_excerpt:el.outerHTML.slice(0,500),
        visible:!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length),
        aria_disabled:el.getAttribute("aria-disabled")
      }));
      try {
        // Await BOTH outcomes. A failed click must not leave an unhandled
        // waitForEvent rejection when the browser is closed.
        const attempts=await Promise.allSettled([
          page.waitForEvent("download",{timeout:22000}),
          button.click({timeout:15000}),
        ]);
        result.click_status=attempts[1].status;
        result.source_network_observations=observedNetwork;
        if(attempts[0].status!=="fulfilled"||attempts[1].status!=="fulfilled"){
          result.download_status="DOWNLOAD_CONTROL_DID_NOT_PRODUCE_FILE";
          result.reason=attempts.map((x,i)=>
            x.status==="rejected" ?
             ((i===0?"download:":"click:")+String(x.reason?.message??x.reason).slice(0,650))
             : null).filter(Boolean).join(" / ");
          done();
        }else{
        const download=attempts[0].value;
        const suggested=download.suggestedFilename();
        const sanitized=suggested.replace(/[^A-Za-z0-9._-]/g,"_").slice(0,96);
        mkdirSync(ROOT,{recursive:true});
        const filepath=path.join(ROOT,sanitized||"official-export.bin");
        await download.saveAs(filepath);
        const bytes=readFileSync(filepath);
        result.download_status="OFFICIAL_EXPORT_BYTES_RETRIEVED_FORMAT_UNVERIFIED";
        result.suggested_filename=sanitized;
        result.file_bytes=bytes.length;
        result.file_sha256=createHash("sha256").update(bytes).digest("hex");
        result.download_protocol=new URL(download.url()).protocol;
        result.first_64_byte_hex=bytes.subarray(0,64).toString("hex");
        result.full_60_month_NAV_validated=false;
        done();
        }
      }catch(ex){
        result.download_status="DOWNLOAD_CONTROL_DID_NOT_PRODUCE_FILE";
        result.reason=ex?.name??"UnknownError";
        done();
      }
    }
  }
} catch(ex) {
  result.download_status="PUBLIC_SITE_OR_BROWSER_UNAVAILABLE";
  result.reason=ex?.name??"UnknownError";
  done();
} finally {
  await browser?.close();
}
