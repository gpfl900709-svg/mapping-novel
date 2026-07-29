from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from public_mapping import PUBLIC_REFERENCE_COLUMNS, build_public_reference_frame, load_public_reference


DEFAULT_SOURCE = REPO_ROOT / "data" / "kiss_payment_settlement_s2_lookup.csv"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "public_s2_mapping_reference.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the PII-free public S2 mapping reference.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Validate the existing output without rewriting it.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        frame = load_public_reference(args.output)
        print(f"ok rows={len(frame)} columns={list(frame.columns)}")
        return 0

    source = pd.read_csv(
        args.source,
        dtype=object,
        keep_default_na=False,
        usecols=list(PUBLIC_REFERENCE_COLUMNS),
    )
    public = build_public_reference_frame(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    public.to_csv(args.output, index=False, encoding="utf-8")
    verified = load_public_reference(args.output)
    print(f"wrote rows={len(verified)} columns={list(verified.columns)} path={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
