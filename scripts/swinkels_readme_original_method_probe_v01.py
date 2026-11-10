"""One-shot official publisher Readme.pdf methodology probe, no market-data export.

Downloads only DataverseNL datafile 512631 over permitted HTTPS and uses the
system pdftotext program; emits redacted short lines, counts and source SHA.
No trading, source schedules, credentials, database or ODS contents.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, SourceUnavailable, fetch,
)

README_FILE_ID = 512631
EXPECTED_PDF_SIZE = 127043
MAX_PDF_BYTES = 500000
MAX_TEXT_BYTES = 400000
KEYWORDS = re.compile(r"return\s*m|percentage|percent|decimal|coupon|reinvest|unit|formula|yield", re.I)


def main():
    if shutil.which("pdftotext") is None:
        raise SourceUnavailable("pdftotext utility unavailable on CI runner")
    pdf = fetch(PUBLISHER + "/api/access/datafile/" + str(README_FILE_ID), MAX_PDF_BYTES)
    if len(pdf) != EXPECTED_PDF_SIZE or not pdf.startswith(b"%PDF-"):
        raise SourceUnavailable("official publisher Readme PDF length or magic mismatch")
    done = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=pdf, capture_output=True, timeout=25, check=False,
    )
    if done.returncode != 0 or not done.stdout or len(done.stdout) > MAX_TEXT_BYTES:
        raise SourceUnavailable("PDF text extraction failed or exceeded research bound")
    lines = done.stdout.decode("utf-8", errors="replace").splitlines()
    # These previews guide manual inspection only; do not self-certify units.
    relevant = []
    for line in lines:
        if KEYWORDS.search(line):
            clean = re.sub(r"\b\d+(?:[.,]\d+)?\b", "[number]", line.strip())
            clean = re.sub(r"\s+", " ", clean)
            if clean:
                relevant.append(clean[:170])
    print("OFFICIAL_README_SOURCE=DataverseNL")
    print("OFFICIAL_README_DATAFILE_ID=" + str(README_FILE_ID))
    print("OFFICIAL_README_BYTES=" + str(len(pdf)))
    print("OFFICIAL_README_SHA256=" + hashlib.sha256(pdf).hexdigest())
    print("OFFICIAL_README_TEXT_EXTRACTED=true")
    print("OFFICIAL_README_KEYWORD_LINE_COUNT=" + str(len(relevant)))
    print("OFFICIAL_README_REDACTED_REVIEW_LINES_START")
    for line in relevant[:12]:
        print(line)
    print("OFFICIAL_README_REDACTED_REVIEW_LINES_END")
    print("RETURN_M_UNITS_CERTIFIED=false")
    print("MODEL_QUALIFIED_SERIES=0")
    print("M1_M2_M3=HOLD_CASH")


if __name__ == "__main__":
    try:
        main()
    except (SourceUnavailable, subprocess.TimeoutExpired) as exc:
        print("OFFICIAL_README_REVIEW=BLOCKED: " + str(exc))
        sys.exit(2)
