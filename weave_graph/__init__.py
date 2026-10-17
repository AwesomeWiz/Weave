"""Import bridge for Antony's graph package.

The FastAPI application already owns ``app.graph`` (a gateway module).
Expose the original teammate package under a distinct name without copying it.
"""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[1] / "app" / "graph")]
