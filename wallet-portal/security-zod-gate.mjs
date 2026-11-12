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

function hasSupportedZod4Range(range, resolvedVersion) {
  // Conservative, exact allowlist of supported semver forms. Do not infer
  // compatibility from a ^4 substring inside a range that also excludes the
  // resolved patched version, e.g. ">=4.0.0 <4.6.6".
  if (typeof range !== "string" || !patchedZodVersion(resolvedVersion)) return false;
  const version = resolvedVersion.match(/^(\d+)\.(\d+)\.(\d+)/).slice(1).map(Number);
  return range.split(/\s*\|\|\s*/).some(part => {
    const caret = /^\^4\.(\d+)\.(\d+)$/.exec(part.trim());
    const minimum = /^>=\s*4\.(\d+)\.(\d+)$/.exec(part.trim());
    const exact = /^4\.(\d+)\.(\d+)$/.exec(part.trim());
    const spec = caret || minimum || exact;
    if (!spec) return false;
    const lower = [4, Number(spec[1]), Number(spec[2])];
    const ge = version[0] > lower[0] ||
      (version[0] === lower[0] &&
       (version[1] > lower[1] ||
        (version[1] === lower[1] && version[2] >= lower[2])));
    if (exact) return version[0] === 4 &&
      version[1] === lower[1] && version[2] === lower[2];
    return ge;
  });
}

function resolveInstalledZod(packages, sdkPath) {
  // Follow Node's nearest-ancestor node_modules resolution order; checking
  // root Zod first could falsely validate an incompatible nested resolution.
  let cursor = sdkPath;
  while (cursor) {
    const candidate = `${cursor}/node_modules/zod`;
    if (Object.hasOwn(packages, candidate)) return packages[candidate];
    const separator = cursor.lastIndexOf("/node_modules/");
    if (separator < 0) break;
    cursor = cursor.slice(0, separator);
  }
  return packages["node_modules/zod"] ?? null;
}

export function assessZodLock(lock) {
  const findings = [];
  const packages = lock && typeof lock === "object" ? lock.packages : null;
  if (!packages || typeof packages !== "object" || Array.isArray(packages)) {
    return { schema: SCHEMA, status: "BLOCKED", findings: ["LOCKFILE_PACKAGES_INVALID"] };
  }
  const root = packages[""];
  const base = packages["node_modules/@base-org/account"];
  if (!root || typeof root !== "object" ||
      typeof root.dependencies?.["@base-org/account"] !== "string") {
    findings.push("BASE_ACCOUNT_ROOT_DEPENDENCY_NOT_VERIFIABLE");
  }
  if (!base || typeof base.dependencies?.["@coinbase/cdp-sdk"] !== "string") {
    findings.push("BASE_ACCOUNT_SDK_EDGE_NOT_VERIFIABLE");
  }
  const validPackageVersion = version =>
    typeof version === "string" && /^\d+\.\d+\.\d+(?:\+[0-9A-Za-z.-]+)?$/.test(version);
  if (!validPackageVersion(base?.version)) {
    findings.push("BASE_ACCOUNT_VERSION_NOT_VERIFIABLE");
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

  // Scan ALL SDK copies, not only the hoisted top-level one. A nested
  // @base-org/account/node_modules/@coinbase/cdp-sdk takes precedence in
  // Node resolution. Every installed SDK copy must have a valid version
  // and a declared Zod-4 range compatible with its actual resolved copy.
  const sdkEntries = Object.entries(packages).filter(
    ([name]) => /(?:^|\/)node_modules\/@coinbase\/cdp-sdk$/.test(name)
  );
  if (sdkEntries.length === 0) {
    findings.push("CDP_SDK_PACKAGE_NOT_VERIFIABLE");
  }
  for (const [name, sdk] of sdkEntries) {
    if (!validPackageVersion(sdk?.version)) {
      findings.push(`CDP_SDK_VERSION_NOT_VERIFIABLE:${name}`);
    }
    const scopedZod = resolveInstalledZod(packages, name);
    if (!scopedZod || !hasSupportedZod4Range(sdk?.dependencies?.zod, scopedZod.version)) {
      findings.push(`CDP_SDK_ZOD4_COMPATIBILITY_NOT_DECLARED:${name}`);
    }
  }
  return {
    schema: SCHEMA,
    status: findings.length ? "BLOCKED" : "PASS_STATIC_LOCKFILE_ONLY",
    findings: findings.sort(),
    checked_zod_package_count: zodEntries.length,
    checked_sdk_package_count: sdkEntries.length,
    sdk_zod_dependency_ranges: sdkEntries.map(([name, sdk]) => ({
      path: name, range: sdk?.dependencies?.zod ?? "UNAVAILABLE",
    })),
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
