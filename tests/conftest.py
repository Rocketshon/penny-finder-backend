"""Shared pytest helpers."""
from __future__ import annotations

import sys
from pathlib import Path

# Let tests import top-level modules (schema, aggregator, heat, ...) without packaging gymnastics.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
