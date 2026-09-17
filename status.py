#!/usr/bin/env python3
"""CLI to view recent deployment history.

Usage:
    python status.py            # show 10 most recent deployments
    python status.py -n 25      # show 25 most recent
    python status.py -v         # also show captured output per deployment
"""
import argparse

from config import Config
from history import DeploymentHistory


def format_row(row):
    if row["success"]:
        status = "SUCCESS"
    elif row["rolled_back"]:
        status = "ROLLED BACK"
    else:
        status = "FAILED"
    before = (row["commit_before"] or "")[:8]
    after = (row["commit_after"] or "")[:8]
    return "[{:>4}] {}  {:<8}  {} -> {}  {}".format(
        row["id"], row["timestamp"], row["trigger_source"], before, after, status
    )


def main():
    parser = argparse.ArgumentParser(description="View auto-deploy-bot deployment history")
    parser.add_argument(
        "-n", "--limit", type=int, default=10, help="number of recent deployments to show"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show full output for each deployment"
    )
    args = parser.parse_args()

    config = Config.from_env()
    history = DeploymentHistory(config.history_db)
    rows = history.recent(limit=args.limit)

    if not rows:
        print("No deployments recorded yet.")
        return

    for row in rows:
        print(format_row(row))
        if args.verbose:
            print("  output:")
            for line in (row["output"] or "").splitlines():
                print("    " + line)


if __name__ == "__main__":
    main()
