/**
 * Offline, fail-closed lockfile advisory gate for wallet-portal.
 *
 * This does NOT prove runtime compatibility, exploit reachability, or release
 * approval. It only refuses known vulnerable Zod versions and incompatible SDK
 * dependency declarations. No npm install, network, credentials or wallet calls.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

const MIN_PATCHED = [4, 6, 6];
const SCHEMA = "ISL_WALLET_ZOD_ADVISORY_LOCK_GATE_V01";

export function patchedZodVersion(version) {
  if (typeof version !== "string") return false;
  // Reject prereleases and unknown future major ranges until explicitly reviewed.
  const match = /^(\d+)\.(\d+)\.(\d+)(?:\+[0-9A-Za-z.-]+)?$/.exec(version);
  if (!match) return false;
  const semver = match.slice(1, 4).map(Number);
  return semver[0] === 4 && (
    semver[1] > MIN_PATCHED[1] ||
    (semver[1] === MIN_PATCHED[1] && semver[2] >= MIN_PATCHED[2])
  );
}

function hasSupportedZod4Range(range) {
  // Do not accept a patched lock when upstream declares only Zod 3.
  // This is a minimal recognition gate, not a complete semver solver.
  return typeof range === "string" &&
    /(?:\^4\.[0-9]+\.[0-9]+|>=\s*4\.[0-9]+\.[0-9]+)/.test(range);
}

export function assessZodLock(lock) {
  const findings = [];
  const packages = lock && typeof lock === "object" ? lock.packages : null;
  if (!packages || typeof packages !== "object" || Array.isArray(packages)) {
    return { schema: SCHEMA, status: "BLOCKED", findings: ["LOCKFILE_PACKAGES_INVALID"] };
  }
  const root = packages[""];
  const base = packages["node_modules/@base-org/account"];
  const sdk = packages["node_modules/@coinbase/cdp-sdk"];
  if (!root || typeof root !== "object" ||
      typeof root.dependencies?.["@base-org/account"] !== "string") {
    findings.push("BASE_ACCOUNT_ROOT_DEPENDENCY_NOT_VERIFIABLE");
  }
  if (!base || typeof base.dependencies?.["@coinbase/cdp-sdk"] !== "string") {
    findings.push("BASE_ACCOUNT_SDK_EDGE_NOT_VERIFIABLE");
  }
  if (!sdk || typeof sdk !== "object" ||
      typeof sdk.version !== "string") {
    findings.push("CDP_SDK_PACKAGE_NOT_VERIFIABLE");
  }
  const range = sdk?.dependencies?.zod;
  if (!hasSupportedZod4Range(range)) {
    findings.push("CDP_SDK_ZOD4_COMPATIBILITY_NOT_DECLARED");
  }
  const zodEntries = Object.entries(packages).filter(
    ([name]) => /(?:^|\/)node_modules\/zod$/.test(name)
  );
  if (zodEntries.length === 0) {
    findings.push("ZOD_RESOLUTION_NOT_VERIFIABLE");
  }
  for (const [name, entry] of zodEntries) {
    if (!patchedZodVersion(entry?.version)) {
      findings.push(`ZOD_UNPATCHED_OR_UNVERIFIED:${name}:${entry?.version ?? "UNKNOWN"}`);
    }
  }
  return {
    schema: SCHEMA,
    status: findings.length ? "BLOCKED" : "PASS_STATIC_LOCKFILE_ONLY",
    findings: findings.sort(),
    checked_zod_package_count: zodEntries.length,
    sdk_zod_dependency_range: typeof range === "string" ? range : "UNAVAILABLE",
    advisory: "GHSA-mrhx-c7xc-m3w5",
    does_not_authorize_release_or_financial_operations: true,
  };
}

function main() {
  const lockfile = resolve(dirname(fileURLToPath(import.meta.url)), "package-lock.json");
  let report;
  try {
    report = assessZodLock(JSON.parse(readFileSync(lockfile, "utf8")));
  } catch {
    report = { schema: SCHEMA, status: "BLOCKED", findings: ["LOCKFILE_UNREADABLE_OR_INVALID"] };
  }
  console.log(JSON.stringify(report));
  if (report.status !== "PASS_STATIC_LOCKFILE_ONLY") process.exitCode = 2;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
