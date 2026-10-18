"""Scheduled agent entrypoint for a **dedicated limited DB role**.

Never imports or uses brokerage APIs. Reads revisioned, previously ingested
prices and writes only research/paper intents, not portfolio fills.
Requires NEON_DATABASE_URL, provided only as a GitHub Actions secret.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from .autonomous_agent import run_cycle, evaluate_hypothesis
from .agent_cli import report
from .provenance import canonical_json



# Dedicated *staging* endpoint: do not accidentally point research at main.
STAGING_HOST = "ep-summer-star-ba5trfu5.c-8.eu-central-1.aws.neon.tech"
STAGING_ROLE = "isl_agent_staging_limited"
STAGING_DATABASE = "investment_lab"


def validate_staging_dsn(dsn: str) -> None:
    """Refuse owner credentials, pooled/main hosts, weak TLS or missing auth."""
    if not dsn:
        raise ValueError("Missing research-only staging connection secret")
    from psycopg.conninfo import conninfo_to_dict
    try:
        uri = urlsplit(dsn)
        if uri.scheme not in ("postgresql", "postgres"):
            raise ValueError("Expected PostgreSQL URI")
        if uri.hostname != STAGING_HOST or uri.port not in (None, 5432):
            raise ValueError("Unexpected Neon staging endpoint")
        data = conninfo_to_dict(dsn)
    except Exception:
        # Parsing errors can contain secrets: never propagate those messages.
        raise ValueError("Invalid research staging connection settings") from None
    if data.get("host") != STAGING_HOST:
        raise ValueError("Unexpected staging compute")
    if data.get("user") != STAGING_ROLE or data.get("dbname") != STAGING_DATABASE:
        raise ValueError("Unexpected staging identity")
    if not data.get("password"):
        raise ValueError("Missing staging authentication")
    if data.get("sslmode") != "verify-full":
        raise ValueError("TLS peer and hostname verification required")
    if any(data.get(k) for k in ("hostaddr", "service", "passfile")):
        raise ValueError("Indirect connection settings prohibited")


def scheduled_cutoff(now: datetime) -> datetime:
    """Stable 07:00 UTC daily cutoff makes retries deterministic."""
    if now.tzinfo is None:
        raise ValueError("UTC-aware now required")
    now = now.astimezone(timezone.utc)
    cutoff = now.replace(hour=7, minute=0, second=0, microsecond=0)
    return cutoff if cutoff <= now else cutoff - timedelta(days=1)


def load_observations(cur, as_of: datetime) -> list[dict]:
    """Public availability AND local receipt time must precede autonomous cycle.

    The returned effective_available_at is at least the source retrieval and ingestion timestamps.
    A late-loaded older PDF must not leak retrospectively into an earlier
    autonomous cycle; v.recorded_at and d.retrieved_at are checked explicitly.
    """
    # Pick the latest eligible revision only AFTER excluding late ingestions.
    # A later-imported correction must never hide an earlier valid revision.
    cur.execute("""
      SELECT DISTINCT ON (v.instrument_code,v.source_code,v.observed_for,v.interval_code)
             v.instrument_code,v.source_code,v.observed_for,v.interval_code,
             v.price_value,v.value_concept,v.revision_no,
             GREATEST(v.available_at,
                 CASE WHEN d.publication_precision='DAY'
                      THEN (((d.published_at AT TIME ZONE 'UTC')::date+1)::timestamp AT TIME ZONE 'UTC')
                      ELSE d.published_at END, v.recorded_at, d.retrieved_at) AS effective_available_at,
             d.canonical_url,d.sha256_hex,d.published_at,d.publication_precision
      FROM investment_lab.price_observation_versions AS v
      JOIN investment_lab.source_documents AS d ON d.document_id=v.document_id
      WHERE d.source_code=v.source_code
        AND v.recorded_at<=%s AND d.retrieved_at<=%s
        AND GREATEST(v.available_at,
                 CASE WHEN d.publication_precision='DAY'
                      THEN (((d.published_at AT TIME ZONE 'UTC')::date+1)::timestamp AT TIME ZONE 'UTC')
                      ELSE d.published_at END, v.recorded_at, d.retrieved_at)<=%s
      ORDER BY v.instrument_code,v.source_code,v.observed_for,v.interval_code,
               GREATEST(v.available_at,
                 CASE WHEN d.publication_precision='DAY'
                      THEN (((d.published_at AT TIME ZONE 'UTC')::date+1)::timestamp AT TIME ZONE 'UTC')
                      ELSE d.published_at END, v.recorded_at, d.retrieved_at) DESC,
               v.revision_no DESC
    """,(as_of,as_of,as_of))
    rows=[]
    for inst,src,dt,iv,px,concept,rev,available,url,sha,published,precision in cur.fetchall():
        rows.append({"instrument_code":inst,"source_code":src,
                     "observed_for":dt.isoformat(),"interval_code":iv,"price_value":str(px),
                     "value_concept":concept,"revision_no":rev,"available_at":available.isoformat(),
                     "document":{"canonical_url":url,"sha256_hex":sha,
                                 "published_at":published.isoformat(),"publication_precision":precision}})
    return rows


def store_cycle(cur,result: dict) -> bool:
    """Transactional journal. Same key+hash is harmless replay; mismatch raises."""
    # Atomic insert-first idempotency. Row locks requiring UPDATE grants
    # are unnecessary and incompatible with an append-only journal role.
    cur.execute("""INSERT INTO investment_lab.agent_cycles
      (run_key,as_of,input_sha256,code_version,records_seen,summary)
      VALUES(%s,%s,%s,%s,%s,%s::jsonb)
      ON CONFLICT (run_key) DO NOTHING
      RETURNING input_sha256""",
      (result["run_key"],result["as_of"],result["input_sha256"],
       result["code_version"],result["observations_available"],
       canonical_json({"hypotheses":len(result["hypotheses"]),"paper_decisions":len(result["paper_decisions"]),"no_live_execution":True})))
    inserted=cur.fetchone()
    if inserted is None:
        # After a concurrent INSERT wait, this fresh statement sees the
        # committed competing writer without an UPDATE lock.
        cur.execute("SELECT input_sha256 FROM investment_lab.agent_cycles WHERE run_key=%s",
                    (result["run_key"],))
        existing=cur.fetchone()
        if existing is None or existing[0] != result["input_sha256"]:
            raise ValueError("Cycle collision: same run_key with changed input; refusing overwrite")
        return False
    for d in result["paper_decisions"]:
        cur.execute("""INSERT INTO investment_lab.agent_paper_decisions
            (run_key,model_code,signal_cutoff,decision_type,target_weights,missing_data,explanation,paper_only)
            VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,true)""",
            (result["run_key"],d["model_code"],d["signal_cutoff"],d["decision_type"],
             canonical_json(d["target_weights"]),canonical_json(d["missing_data"]),d["explanation"]))
    for h in result["hypotheses"]:
        cur.execute("""INSERT INTO investment_lab.agent_hypotheses
          (hypothesis_key,originating_run,instrument_code,generated_as_of,observation_date,
           reference_value,predicted_direction,statement,falsification,evidence_fingerprint)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT(hypothesis_key) DO NOTHING""",
          (h["hypothesis_key"],result["run_key"],h["instrument_code"],h["as_of"],
           h["observation_date"],h["reference_value"],h["direction"],h["statement"],
           h["falsification"],h["source_fingerprint"]))
    return True


def evaluate_pending(cur, observations: list[dict], as_of: datetime) -> int:
    cur.execute("""SELECT h.hypothesis_key,h.instrument_code,h.observation_date,
                         h.reference_value,h.predicted_direction
       FROM investment_lab.agent_hypotheses h
       LEFT JOIN investment_lab.agent_hypothesis_evaluations e USING (hypothesis_key)
       WHERE e.hypothesis_key IS NULL AND h.generated_as_of<%s""",(as_of,))
    count=0
    for key,inst,obs_date,ref,direction in cur.fetchall():
        h={"hypothesis_key":key,"instrument_code":inst,
           "observation_date":obs_date.isoformat(),"reference_value":str(ref),"direction":direction}
        out=evaluate_hypothesis(h,observations,as_of.isoformat())
        if out["status"]!="EVALUATED":
            continue
        cur.execute("""INSERT INTO investment_lab.agent_hypothesis_evaluations
           (hypothesis_key,evaluated_as_of,actual_observed_for,actual_value,direction_correct,evaluation_note)
           VALUES(%s,%s,%s,%s,%s,%s)
           ON CONFLICT(hypothesis_key) DO NOTHING""",
           (key,as_of,out["actual_observation"],out["actual_value"],
            out["direction_correct"],"First subsequently published month used; preliminary directional experiment only"))
        count+=1
    return count



def assert_research_runtime(cur) -> None:
    """Fail closed if GitHub points at an owner, ingester or broad DB identity.

    Checks actual database privileges, not only a role name in configuration.
    Required evidence is SELECT-only; journal is INSERT+SELECT with no UPDATE.
    """
    cur.execute("""
      SELECT
        has_schema_privilege(current_user,'investment_lab','USAGE'),
        NOT has_schema_privilege(current_user,'investment_lab','CREATE'),
        NOT has_database_privilege(current_user,current_database(),'CREATE'),
        has_table_privilege(current_user,'investment_lab.source_documents','SELECT'),
        has_table_privilege(current_user,'investment_lab.price_observation_versions','SELECT'),
        NOT has_table_privilege(current_user,'investment_lab.source_documents','INSERT'),
        NOT has_table_privilege(current_user,'investment_lab.price_observation_versions','INSERT'),
        has_table_privilege(current_user,'investment_lab.agent_cycles','SELECT'),
        has_table_privilege(current_user,'investment_lab.agent_cycles','INSERT'),
        NOT has_table_privilege(current_user,'investment_lab.agent_cycles','UPDATE'),
        NOT has_table_privilege(current_user,'investment_lab.agent_cycles','DELETE'),
        has_table_privilege(current_user,'investment_lab.agent_paper_decisions','INSERT'),
        has_table_privilege(current_user,'investment_lab.agent_hypotheses','INSERT'),
        has_table_privilege(current_user,'investment_lab.agent_hypothesis_evaluations','INSERT'),
        NOT has_table_privilege(current_user,'investment_lab.pipeline_runs','INSERT')
    """)
    permissions=cur.fetchone()
    if not permissions or not all(permissions):
        raise RuntimeError("Unsafe PostgreSQL research role: required least-privilege boundary failed")


def execute(dsn: str, out_dir: Path, now: datetime) -> dict:
    try:
        import psycopg  # Installed in isolated GitHub job, not a runtime requirement for offline tests.
    except ImportError as exc:
        raise RuntimeError("psycopg is required for autonomous Neon scheduling") from exc
    validate_staging_dsn(dsn)
    cutoff=scheduled_cutoff(now)
    with psycopg.connect(dsn,connect_timeout=15,sslmode="verify-full",
                         sslrootcert="/etc/ssl/certs/ca-certificates.crt",
                         autocommit=False) as conn:
        with conn.cursor() as cur:
            assert_research_runtime(cur)
            price_rows=load_observations(cur,cutoff)
            if len(price_rows) != 1:
                raise RuntimeError("Staging canary expected exactly one public PIT record")
            job={"run_key":f"daily-research-{cutoff:%Y-%m-%d}","as_of":cutoff.isoformat(),
                 "code_version":"2.0.0-rc1","observations":price_rows,"requirements":{}}
            result=run_cycle(job)
            if (len(result["paper_decisions"]) != 3 or result["hypotheses"]
                or result["paper_fills_created"] != 0 or result["real_orders_created"] != 0
                or any(d["decision_type"] != "HOLD_CASH" or d["target_weights"]
                       for d in result["paper_decisions"])):
                raise RuntimeError("Only three synthetic HOLD_CASH intents are allowed")
            newly_written=store_cycle(cur,result)
            evaluations=evaluate_pending(cur,price_rows,cutoff)
            result["newly_written"]=newly_written
            result["evaluated_hypotheses"]=evaluations
        conn.commit()
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/"cycle.json").write_text(canonical_json(result)+"\n",encoding="utf-8")
    (out_dir/"report.md").write_text(report(result),encoding="utf-8")
    return result


# Fixed date, used only by an explicitly invoked staging-only Actions job.
CANARY_NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def main() -> None:
    parser=argparse.ArgumentParser(description="MANUAL staging HOLD_CASH research cycle only")
    parser.add_argument("--fixed-staging-canary", action="store_true", required=True)
    parser.add_argument("--out-dir",default="artifacts/staging-full-runner")
    args=parser.parse_args()
    try:
        dsn=os.environ.get("NEON_DATABASE_URL","")
        # Reuse already verified staging preflight on main, including client TLS,
        # exact DB identity, privileges and a staging-only database marker.
        from scripts.staging_preflight import check_connection
        check_connection(dsn)
        out_dir=Path(args.out_dir)
        first=execute(dsn,out_dir,CANARY_NOW)
        second=execute(dsn,out_dir,CANARY_NOW)
        if (not first["newly_written"] or second["newly_written"]
            or first["input_sha256"] != second["input_sha256"]
            or first["paper_decisions"] != second["paper_decisions"]
            or first["evaluated_hypotheses"] != 0 or second["evaluated_hypotheses"] != 0):
            raise RuntimeError("Unexpected duplicate, changed fingerprint or hypothesis evaluation")
        summary={"status":"FULL_RESEARCH_RUNNER_STAGING_VERIFIED",
                 "run_key":first["run_key"],"as_of":first["as_of"],
                 "input_sha256":first["input_sha256"],
                 "records_seen":first["observations_available"],
                 "paper_decisions":len(first["paper_decisions"]),
                 "all_hold_cash":True,"first_write":True,"replay_write":False,
                 "paper_fills":0,"real_orders":0,"scheduled":False}
        (out_dir/"manifest.json").write_text(canonical_json(summary)+"\n",encoding="utf-8")
    except Exception as e:
        # psycopg exceptions may include DSNs, never log their raw contents.
        print("FULL_STAGING_RUNNER_FAILED: "+type(e).__name__,file=sys.stderr)
        raise SystemExit(2) from None
    print("FULL_RESEARCH_RUNNER_STAGING_VERIFIED",summary["run_key"],
          "records",summary["records_seen"],"HOLD_CASH",summary["paper_decisions"],
          "replay_new_rows",0,"real_orders",0)


if __name__=="__main__":
    main()
