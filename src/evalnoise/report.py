"""Turn an analysis into something a person reads, or a machine parses."""

from __future__ import annotations

import json


def _points(value: float) -> str:
    return f"{value * 100:+.1f}"


def render_text(analysis: dict) -> str:
    change = analysis["change"]
    items = analysis["items"]
    lines = [
        f"items          {items['paired']} paired   "
        f"({items['unmatched_baseline'] + items['unmatched_variant']} unmatched)",
    ]
    noise = analysis["noise_floor"]
    if noise:
        lines.append(
            f"noise floor    ±{noise['band'] * 100:.1f} points  "
            f"churn {noise['churn_rate']:.0%}  ({noise['churn_count']} flipped)"
        )
    else:
        lines.append("noise floor    not measured — no --aa pair was supplied")
    lines += [
        f"your change    {_points(change['delta'])} points  "
        f"churn {change['churn_rate']:.0%}  ({change['churn_count']} flipped: "
        f"{change['gains']} gained, {change['losses']} lost)",
        f"               95% CI [{_points(change['ci_low'])}, {_points(change['ci_high'])}]   "
        f"McNemar p = {change['p_value']:.2f}",
        f"               smallest effect this setup could detect: "
        f"±{change['critical'] * 100:.1f} points",
        "",
        f"VERDICT  {analysis['verdict']['name']}",
        f"         {analysis['verdict']['reason']}",
    ]
    return "\n".join(lines)


def render_json(analysis: dict) -> str:
    return json.dumps(analysis, indent=1, sort_keys=True)
