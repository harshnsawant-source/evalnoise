"""The command line: arguments in, a verdict and an exit code out."""

from __future__ import annotations

import argparse
import sys

from evalnoise import __version__, stats
from evalnoise.load import LoadError, load_run, pair
from evalnoise.report import render_json, render_text
from evalnoise.verdict import analyse

USAGE_ERROR = 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evalnoise",
        description=(
            "Decide whether a change is real or inside the noise your setup already produces."
        ),
    )
    parser.add_argument("--version", action="version", version=f"evalnoise {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="compare two runs")
    check.add_argument("--baseline", required=True, help="results for configuration A")
    check.add_argument("--variant", required=True, help="results for configuration B")
    check.add_argument("--aa", help="a second run of A, or a placebo change: the noise floor")
    check.add_argument(
        "--epsilon",
        type=float,
        default=0.0,
        help="for numeric scores, the move below which nothing counts as changed",
    )
    check.add_argument("--alpha", type=float, default=0.05, help="significance level (default 0.05)")
    check.add_argument("--seed", type=int, default=stats.DEFAULT_SEED, help="random seed")
    check.add_argument("--json", action="store_true", help="print the analysis as JSON")
    check.set_defaults(func=_check)
    return parser


def _validate(args: argparse.Namespace) -> None:
    """Refuse settings that would make the report state falsehoods.

    A negative epsilon counts every item as both a gain and a loss, so the report would
    print "100 flipped: 100 gained, 100 lost" on 100 items; an alpha near 1 calls almost
    anything real. Neither is a judgement call the tool should make silently.
    """
    if args.epsilon < 0:
        raise LoadError(f"--epsilon must not be negative (got {args.epsilon})")
    if not 0 < args.alpha <= 0.5:
        raise LoadError(f"--alpha must be above 0 and at most 0.5 (got {args.alpha})")


def _check(args: argparse.Namespace) -> int:
    _validate(args)
    baseline = load_run(args.baseline)
    variant = load_run(args.variant)
    paired_ab = pair(baseline, variant)
    paired_aa = pair(baseline, load_run(args.aa)) if args.aa else None
    analysis = analyse(paired_ab, paired_aa, epsilon=args.epsilon, seed=args.seed, alpha=args.alpha)
    print(render_json(analysis) if args.json else render_text(analysis))
    return analysis["verdict"]["exit_code"]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except LoadError as exc:
        print(f"evalnoise: {exc}", file=sys.stderr)
        return USAGE_ERROR
    except Exception as exc:  # noqa: BLE001 - see below
        #: An uncaught exception exits 1, which is the code for INSIDE_NOISE: a CI job
        #: branching on the exit code could not tell "your change is noise" from "the
        #: tool crashed". Anything unexpected is reported as an input error instead.
        print(f"evalnoise: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return USAGE_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
