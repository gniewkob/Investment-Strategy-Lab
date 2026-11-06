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
      const button=terms.first();
      await button.scrollIntoViewIfNeeded({timeout:15000});
      try {
        const promise=page.waitForEvent("download",{timeout:30000});
        await button.click({timeout:20000});
        const download=await promise;
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
