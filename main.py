from __future__ import annotations

import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

for _m in [k for k in list(sys.modules) if k == "app" or k.startswith(("handlers_", "models_", "panels_"))]:
    del sys.modules[_m]
for _m in ("panels",):
    sys.modules.pop(_m, None)

from app import ext, chat  # noqa: F401

import handlers_proxmox  # noqa: F401
import panels  # noqa: F401
