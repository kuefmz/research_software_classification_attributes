#!/usr/bin/env python3
"""Run the complete reproducible base data-preparation pipeline.

This orchestrator intentionally stops before GitHub README fetching and SoMEF
extraction. It creates the cleaned PwC and bio.tools final datasets needed for
the first ML experiments:

1. Align Papers with Code and remove no data yet.
2. Align bio.tools, expanding multiple DOI values to separate records.
3. Enrich bio.tools publication metadata from OpenAlex using cached DOI lookup.
4. Create final ML-ready datasets after the study-specific cleanup rules:
   - remove the non-informative PwC ``General`` label;
   - require GitHub repository URLs for PwC and bio.tools records;
   - require DOI-backed publication records for bio.tools.

For the later README/SoMEF stage, run ``scripts/03_enrich_github_metadata.py``
after this script, then enable ``RUN_SOMEF_ENRICHMENT`` in ``src/config.py`` and
rerun ``scripts/04_create_ml_datasets.py``.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.utils.io_utils import configure_logging

LOGGER = logging.getLogger("run_data_preparation")
ROOT = Path(__file__).resolve().parent.parent


def run_script(script_name: str) -> None:
    """Run one pipeline script with the current Python interpreter."""
    path = ROOT / "scripts" / script_name
    LOGGER.info("Running %s", path)
    subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)


def main() -> None:
    configure_logging()
    for script_name in [
        "01_align_pwc.py",
        "02_align_biotools.py",
        "03_enrich_biotools_publications.py",
        "04_create_ml_datasets.py",
    ]:
        run_script(script_name)
    LOGGER.info("Base data-preparation pipeline complete.")


if __name__ == "__main__":
    main()
