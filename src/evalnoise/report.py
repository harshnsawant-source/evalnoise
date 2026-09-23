"""Turn an analysis into something a person reads, or a machine parses.

The text report stays ASCII on purpose. A Windows console defaults to cp1252, where a
plus-minus sign or an em dash arrives as a replacement character, and a tool whose first
line of output is mojibake has spent its credibility before it says anything.
"""

from __future__ import annotations

import json


def _signed(value: float, analysis: dict) -> str:
    scale = analysis["units"]["scale"]
    return f"{value * scale:+.1f}" if scale != 1.0 else f"{value * scale:+.2f}"


def _size(value: float, analysis: dict) -> str:
    scale = analysis["units"]["scale"]
    return f"{value * scale:.1f}" if scale != 1.0 else f"{value * scale:.2f}"


def _unit(analysis: dict) -> str:
    return f" {analysis['units']['unit']}" if analysis["units"]["unit"] else ""


def _unmatched(items: dict) -> str:
    """Counts by side with example ids: a bare total hides an id-format clash."""
    parts = []
    for side in ("baseline", "variant"):
        count = items[f"unmatched_{side}"]
        if not count:
            continue
        examples = ", ".join(items[f"example_unmatched_{side}"])
        parts.append(f"{count} only in {side} (e.g. {examples})")
    return "; ".join(parts) if parts else "none unmatched"


def render_text(analysis: dict) -> str:
    change = analysis["change"]
    items = analysis["items"]
    unit = _unit(analysis)
    lines = [f"items          {items['paired']} paired   ({_unmatched(items)})"]
    noise = analysis["noise_floor"]
    if noise and noise["band"] is not None:
        measured = f", measured on {noise['paired']} items"
        if noise["unmatched"]:
            measured += f" ({noise['unmatched']} unmatched)"
        lines.append(
            f"noise floor    +/-{_size(noise['band'], analysis)}{unit}  "
            f"churn {noise['churn_rate']:.0%}  ({noise['churn_count']} flipped{measured})"
        )
    elif noise:
        lines.append(
            f"noise floor    unmeasurable - the A/A pair flipped nothing, "
            f"on {noise['paired']} items"
        )
    else:
        lines.append("noise floor    not measured - no --aa pair was supplied")
    lines += [
        f"your change    {_signed(change['delta'], analysis)}{unit}  "
        f"churn {change['churn_rate']:.0%}  ({change['churn_count']} flipped: "
        f"{change['gains']} gained, {change['losses']} lost)",
        f"               95% CI [{_signed(change['ci_low'], analysis)}, "
        f"{_signed(change['ci_high'], analysis)}]   McNemar p = {change['p_value']:.2f}",
        #: Not "the smallest effect you could detect": this is the 95th percentile of what
        #: chance produces here, so an effect equal to it is caught about half the time.
        f"               detection threshold (chance alone reaches this 5% of the time): "
        f"+/-{_size(change['critical'], analysis)}{unit}",
        "",
        f"VERDICT  {analysis['verdict']['name']}",
        f"         {analysis['verdict']['reason']}",
    ]
    return "\n".join(lines)


def render_json(analysis: dict) -> str:
    return json.dumps(analysis, indent=1, sort_keys=True)
