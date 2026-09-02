#!/usr/bin/env python3
"""Build the audit-first candidate canonical paper dataset offline."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.final_dataset_builder import main


if __name__ == "__main__":
    main()
