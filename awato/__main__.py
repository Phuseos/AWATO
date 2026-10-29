"""Entry point: `python -m awato` plays the game, `python -m awato --check` validates content/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import DEFAULT_CONTENT_DIR, ContentError, load_content


def check(content_dir):
    content = load_content(content_dir, strict=False)
    order = {"error": 0, "warning": 1, "info": 2}
    for problem in sorted(content.problems, key=lambda p: order[p.level]):
        print(problem)
    errors = sum(p.level == "error" for p in content.problems)
    warnings = sum(p.level == "warning" for p in content.problems)
    print(f"\n{len(content.events)} events, {len(content.tickets)} tickets, {len(content.locations)} locations, "
          f"{len(content.shop)} shop items, {len(content.endings)} endings")
    print(f"{errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="awato", description="A Week At The Office")
    parser.add_argument("--check", action="store_true", help="validate the content files and exit")
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT_DIR, help="content folder (default: %(default)s)")
    parser.add_argument("--seed", type=int, help="random seed, for reproducible playthroughs")
    args = parser.parse_args(argv)

    if args.check:
        return check(args.content)

    try:
        content = load_content(args.content)
    except ContentError as e:
        print("The content has errors, run with --check for details:\n", file=sys.stderr)
        print(e, file=sys.stderr)
        return 1

    from .ui.app import AwatoApp
    AwatoApp(content, seed=args.seed).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
