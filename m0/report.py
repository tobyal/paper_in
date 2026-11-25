"""Refresh V2 standard files and factual production status."""
import json
from .settings import ROOT
from .storage import Store
from .validation import quality
s=Store(ROOT)
print(json.dumps(quality(s.read()),ensure_ascii=False,indent=2))
