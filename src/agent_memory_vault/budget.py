from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings


class MonthlyBudget:
    def __init__(self, state_root: Path, settings: Settings):
        self.path = state_root / "cost.json"
        self.settings = settings

    @staticmethod
    def current_period() -> str:
        return datetime.now(UTC).strftime("%Y-%m")

    def _read(self) -> dict[str, object]:
        if not self.path.exists():
            return {"periods": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            return {"periods": {}}

    def spent(self) -> float:
        data = self._read()
        periods = data.get("periods", {})
        if not isinstance(periods, dict):
            return 0.0
        current = periods.get(self.current_period(), {})
        return float(current.get("estimated_usd", 0.0)) if isinstance(current, dict) else 0.0

    def exhausted(self) -> bool:
        return self.spent() >= self.settings.monthly_budget_usd

    def record(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = input_tokens * self.settings.input_cost_per_million / 1_000_000
        output_cost = output_tokens * self.settings.output_cost_per_million / 1_000_000
        cost = input_cost + output_cost
        data = self._read()
        periods = data.setdefault("periods", {})
        period = periods.setdefault(
            self.current_period(),
            {"input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0},
        )
        period["input_tokens"] += input_tokens
        period["output_tokens"] += output_tokens
        period["estimated_usd"] = round(float(period["estimated_usd"]) + cost, 8)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
        return cost
