"""Server-sent events of the answer stream (TECH-V2-ai-service §7.2)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PING = ": ping\n\n"  # comment line every 15 s so a proxy does not close an idle connection


@dataclass(frozen=True)
class Event:
    name: str  # meta | delta | replace | refusal | citations | done | error
    data: Any

    def sse(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))
        return f"event: {self.name}\ndata: {payload}\n\n"
