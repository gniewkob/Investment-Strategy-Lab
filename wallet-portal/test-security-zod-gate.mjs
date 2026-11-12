import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { assessZodLock, patchedZodVersion } from "./security-zod-gate.mjs";

const root = dirname(fileURLToPath(import.meta.url));

function fixture({ version = "3.25.76", range = "^3.25.76", nestedVersion } = {}) {
  const packages = {
    "": { dependencies: { "@base-org/account": "2.5.13" } },
    "node_modules/@base-org/account": {
      version: "2.5.13", dependencies: { "@coinbase/cdp-sdk": "^1.56.0" },
    },
    "node_modules/@coinbase/cdp-sdk": {
      version: "1.62.0", dependencies: { zod: range },
    },
    "node_modules/zod": { version },
  };
  if (nestedVersion !== undefined) {
    packages["node_modules/example/node_modules/zod"] = { version: nestedVersion };
  }
  return { name: "fixture", lockfileVersion: 3, packages };
}

test("advisory: Zod 3.x and 4.6.5 are never classified patched", () => {
  for (const version of ["3.25.76", "4.6.5", "4.6.6-rc.1", "5.0.0", "n/a"]) {
    assert.equal(patchedZodVersion(version), false, version);
  }
  for (const version of ["4.6.6", "4.6.7", "4.7.0", "4.10.1"]) {
    assert.equal(patchedZodVersion(version), true, version);
  }
});

test("the actual locked Coinbase SDK path remains blocked until upstream repair", () => {
  const lock = JSON.parse(readFileSync(join(root, "package-lock.json"), "utf8"));
  const result = assessZodLock(lock);
  assert.equal(result.advisory, "GHSA-mrhx-c7xc-m3w5");
  assert.equal(result.does_not_authorize_release_or_financial_operations, true);
  assert.equal(result.schema, "ISL_WALLET_ZOD_ADVISORY_LOCK_GATE_V01");
  // Both outcomes are valid: future upstream remediation must NOT fail this
  // test just because the old vulnerability is gone.
  if (result.status === "BLOCKED") {
    assert.ok(result.findings.length > 0);
  } else {
    assert.equal(result.status, "PASS_STATIC_LOCKFILE_ONLY");
    assert.deepEqual(result.findings, []);
  }
});

test("an unpatched Zod version is blocked, even with a dual SDK range", () => {
  for (const version of ["3.25.76", "4.6.5"]) {
    const result = assessZodLock(fixture({ version, range: "^3.25.76 || ^4.6.6" }));
    assert.equal(result.status, "BLOCKED");
    assert.ok(result.findings.some(f => f.startsWith("ZOD_UNPATCHED_OR_UNVERIFIED:")));
  }
});

test("an SDK declaring Zod 3 only blocks a forged patched lock", () => {
  const result = assessZodLock(fixture({ version: "4.6.7", range: "^3.25.76" }));
  assert.equal(result.status, "BLOCKED");
  assert.ok(result.findings.some(f => f.startsWith("CDP_SDK_ZOD4_COMPATIBILITY_NOT_DECLARED:")));
});

test("a patched Zod 4 with compatible SDK range passes only the static gate", () => {
  const result = assessZodLock(fixture({ version: "4.6.7", range: "^3.25.76 || ^4.6.6" }));
  assert.equal(result.status, "PASS_STATIC_LOCKFILE_ONLY");
  assert.equal(result.does_not_authorize_release_or_financial_operations, true);
  assert.deepEqual(result.findings, []);
});

test("nested vulnerable Zod remains blocked when root Zod is patched", () => {
  const result = assessZodLock(fixture({
    version: "4.6.7", range: "^3.25.76 || ^4.6.6", nestedVersion: "3.25.76",
  }));
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.checked_zod_package_count, 2);
  assert.ok(result.findings.some(f => f.includes("node_modules/example/node_modules/zod")));
});

test("missing manifest edges or missing Zod cannot be mistaken for remediation", () => {
  for (const lock of [
    {},
    { packages: {} },
    { packages: { "": { dependencies: {} }, "node_modules/zod": { version: "4.6.7" } } },
  ]) {
    assert.equal(assessZodLock(lock).status, "BLOCKED");
  }
});

test("a declared Zod-4 range must not exclude the resolved patched version", () => {
  for (const range of [
    "^3.25.76 || >=4.0.0 <4.6.6",
    "^3.25.76 || ^4.8.0",
    ">=4.0.0 <4.6.6",
  ]) {
    const result = assessZodLock(fixture({ version: "4.6.7", range }));
    assert.equal(result.status, "BLOCKED", range);
    assert.ok(result.findings.some(f => f.startsWith("CDP_SDK_ZOD4_COMPATIBILITY_NOT_DECLARED")));
  }
});

test("every installed SDK copy is checked, including the nested Base resolution", () => {
  const lock = fixture({ version: "4.6.7", range: "^3.25.76 || ^4.6.6" });
  lock.packages["node_modules/@base-org/account/node_modules/@coinbase/cdp-sdk"] = {
    version: "1.61.0", dependencies: { zod: "^3.25.76" },
  };
  const result = assessZodLock(lock);
  assert.equal(result.status, "BLOCKED");
  assert.equal(result.checked_sdk_package_count, 2);
  assert.ok(result.findings.some(f =>
    f.includes("node_modules/@base-org/account/node_modules/@coinbase/cdp-sdk")));
});

test("SDK Zod resolution checks every ancestor before the hoisted root copy", () => {
  const lock = fixture({ version: "4.6.7", range: "^3.25.76 || ^4.6.6" });
  const nestedSdk = "node_modules/a/node_modules/b/node_modules/@coinbase/cdp-sdk";
  const nearestZod = "node_modules/a/node_modules/zod";
  lock.packages[nestedSdk] = {
    version: "1.62.0", dependencies: { zod: "4.6.7" },
  };
  lock.packages[nearestZod] = { version: "4.7.0" };
  const wrong = assessZodLock(lock);
  assert.equal(wrong.status, "BLOCKED");
  assert.ok(wrong.findings.some(f =>
    f.includes("CDP_SDK_ZOD4_COMPATIBILITY_NOT_DECLARED:" + nestedSdk)));

  // Node resolves the nearest copy first; a compatible nearer copy
  // supersedes the incompatible intermediate ancestor.
  lock.packages["node_modules/a/node_modules/b/node_modules/zod"] = {
    version: "4.6.7",
  };
  const fixed = assessZodLock(lock);
  assert.equal(fixed.status, "PASS_STATIC_LOCKFILE_ONLY");
});

test("missing or empty versions of Base/SDK are rejected even if Zod is patched", () => {
  for (const variant of ["missing-base", "empty-base", "missing-sdk", "empty-sdk"]) {
    const lock = fixture({ version: "4.6.7", range: "^3.25.76 || ^4.6.6" });
    if (variant === "missing-base") delete lock.packages["node_modules/@base-org/account"].version;
    if (variant === "empty-base") lock.packages["node_modules/@base-org/account"].version = "";
    if (variant === "missing-sdk") delete lock.packages["node_modules/@coinbase/cdp-sdk"].version;
    if (variant === "empty-sdk") lock.packages["node_modules/@coinbase/cdp-sdk"].version = "";
    const result = assessZodLock(lock);
    assert.equal(result.status, "BLOCKED", variant);
    assert.ok(result.findings.some(f => f.includes("VERSION_NOT_VERIFIABLE")), variant);
  }
});

test("CLI reports block as exit code 2, without invoking npm or a wallet", () => {
  const lock = JSON.parse(readFileSync(join(root, "package-lock.json"), "utf8"));
  const result = assessZodLock(lock);
  const cli = spawnSync(process.execPath, [join(root, "security-zod-gate.mjs")], {
    encoding: "utf8", timeout: 10000, env: { PATH: "" },
  });
  assert.equal(cli.error, undefined);
  assert.equal(cli.status, result.status === "BLOCKED" ? 2 : 0);
  const reported = JSON.parse(cli.stdout.trim());
  assert.deepEqual(reported, result);
});
