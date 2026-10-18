"""CLI for durable research artifacts. No network or live financial integration."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .autonomous_agent import run_cycle
from .provenance import canonical_json


def report(result: dict) -> str:
    lines = ["# Investment Strategy Lab — autonomiczny cykl badawczy",
             f"Cykl: `{result['run_key']}`", f"Dane dostępne do: {result['as_of']}",
             f"Uwzględnione rekordy PIT: {result['observations_available']}",
             "", "## Wirtualne decyzje"]
    for dec in result['paper_decisions']:
        lines.append(f"- **{dec['model_code']}**: {dec['decision_type']} — {dec['explanation']}.")
    lines += ["", "## Eksperymenty badawcze", f"Nowe hipotezy do testu: {len(result['hypotheses'])}.",
              "", "Wyniki to edukacyjne badania i paper trading; bez realnych transakcji ani rekomendacji."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out-dir", default="artifacts")
    args = ap.parse_args()
    job = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = run_cycle(job)
    folder = Path(args.out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cycle.json").write_text(canonical_json(result)+"\n", encoding="utf-8")
    (folder / "report.md").write_text(report(result), encoding="utf-8")
    print("AUTONOMOUS_RESEARCH_DRY_RUN", result["run_key"], "paper_decisions", len(result["paper_decisions"]))


if __name__ == "__main__":
    main()
