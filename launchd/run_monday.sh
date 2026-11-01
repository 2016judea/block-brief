#!/bin/zsh
# The Monday job. Keys from bricks/.env, Square ones from the repo's .env; the bricks venv
# has anthropic, duckdb and cryptography. caffeinate keeps the Mac awake for the run.
set -a; . /Users/aidan/Desktop/bricks/.env; . "$(dirname "$0")/repo/.env"; set +a
cd "$(dirname "$0")/repo" || exit 1
echo "== $(date) block-brief monday"
/usr/bin/caffeinate -i /Users/aidan/Desktop/bricks/.venv/bin/python3 pipeline/brief.py --all
