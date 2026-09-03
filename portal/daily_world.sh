#!/bin/sh
# Daily dynamics increment. Does not recrawl vendor case-study walls.
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 portal/ingest_world.py --daily
# --daily includes bounded cs_hubs recrawl (existing vendors, dated stories only).
