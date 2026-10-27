#!/usr/bin/env python3
"""Regenerate the "With OneSearch vs without" comparison table from OneLoop logs.

Every number in that table is derived from files the agent harness writes:

  <repo>/.oneloop/sessions/<id>.jsonl   the conversation (tool calls, prompts)
  <repo>/.oneloop/metrics/<id>.jsonl    per-API-call and per-tool timing/tokens

Metric definitions (this is the whole trick, four numbers):

  Model turns        = number of `api_call` events in metrics. One event is one
                       model round trip. It is NOT the assistant-message count:
                       a turn that only emits tool calls leaves no text message,
                       so the grep arm of medplum reads 29 messages but 34 turns.
  Tool calls         = number of `ToolCall` messages in the session.
  Shell grabs        = bash calls mentioning grep + bash calls mentioning sed +
                       bash calls mentioning find (per bash call, summed, so one
                       command running `grep ... ; sed ...` counts twice).
  Input tokens billed = sum of `input_tokens` over `api_call` events. Each event
                       bills the whole context sent, which is why an arm that
                       re-reads files pays again on every later turn.

Usage:
  python3 scripts/experiment_report.py              # tables + check against README.md
  python3 scripts/experiment_report.py --strict      # ... same, exit 1 on any mismatch (CI)
  python3 scripts/experiment_report.py --no-check    # tables only
  python3 scripts/experiment_report.py --json        # raw computed stats
  python3 scripts/experiment_report.py --scan ~/repos  # every arm found, for new runs

Stdlib only: json, re, os, sys, glob, argparse.
"""

import argparse
import glob
import json
import os
import re
import sys

# ---------------------------------------------------------------- configuration
# One entry per experiment. Paths are relative to the repos dir (--repos).
# Add an entry here when you run a new one; the README row is matched by `name`.
EXPERIMENTS = [
    {
        "name": "VS Code",
        "with_arm": "vscode/.oneloop/sessions/2026-10-23.jsonl",
        "without_arm": "vscode-clone/.oneloop/sessions/2026-10-23.jsonl",
    },
    {
        "name": "Medplum",
        "with_arm": "medplum/.oneloop/sessions/2026-10-24.jsonl",
        "without_arm": "medplum/.oneloop/sessions/2026-10-24-001.jsonl",
    },
    {
        "name": "Vendo",
        "with_arm": "vendo/.oneloop/sessions/2026-10-24.jsonl",
        "without_arm": "vendo/.oneloop/sessions/2026-10-24-001.jsonl",
    },
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
DEFAULT_REPOS = os.path.expanduser("~/repos")

GRAB_TOOLS = ("grep", "sed", "find")   # what counts as a "shell grab"
OS_CALL = re.compile(r"\bos\s+(?:search|batch|related|rel)\b")

# README labels -> keys of a computed stats dict
ROWS = [
    ("Model turns", "turns"),
    ("Tool calls", "tool_calls"),
    ("Shell grabs (`grep`, `sed`, `find`)", "shell_grabs"),
    ("Input tokens billed", "tokens"),
]


# ---------------------------------------------------------------------- reading
def read_jsonl(path):
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def metrics_path(session_path):
    return session_path.replace(os.sep + "sessions" + os.sep, os.sep + "metrics" + os.sep)


def arm_stats(session_path):
    """Compute the four table metrics (plus some context) for one arm."""
    if not os.path.exists(session_path):
        raise SystemExit("no session log at %s (check the paths in EXPERIMENTS or --repos)"
                         % session_path)
    session = read_jsonl(session_path)

    tool_calls = 0
    grabs = 0
    bash_calls = 0
    os_calls = 0
    tools = {}
    question = ""

    for entry in session:
        msg = entry.get("message") or {}
        kind = next(iter(msg), None)
        body = msg.get(kind) or {}

        if kind == "User" and not question:
            question = (body.get("content") or "").strip()
        elif kind == "ToolCall":
            tool_calls += 1
            name = body.get("name", "?")
            tools[name] = tools.get(name, 0) + 1
            # arguments are a dict in current logs, a JSON string in older ones
            args = body.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"command": args}
            if not isinstance(args, dict):
                args = {}
            command = args.get("command")
            command = command if isinstance(command, str) else ""
            if name == "bash":
                bash_calls += 1
                # per bash call, summed: `grep ... ; sed ...` in one command counts twice
                grabs += sum(1 for tok in GRAB_TOOLS
                             if re.search(r"\b" + tok + r"\b", command))
            if OS_CALL.search(command):
                os_calls += 1

    metrics = read_jsonl(metrics_path(session_path)) if os.path.exists(metrics_path(session_path)) else []
    api = [row for row in metrics if row.get("event") == "api_call"]
    assistant_texts = sum(1 for entry in session if "Assistant" in (entry.get("message") or {}))

    # Model turns: api_call events. Fall back to assistant messages if metrics are absent.
    turns = len(api) if api else assistant_texts
    tokens = sum(row.get("input_tokens", 0) or 0 for row in api)

    return {
        "session": session_path,
        "question": question,
        "turns": turns,
        "turns_from_metrics": bool(api),
        "assistant_messages": assistant_texts,
        "tool_calls": tool_calls,
        "shell_grabs": grabs,
        "bash_calls": bash_calls,
        "os_calls": os_calls,
        "tools": tools,
        "tokens": tokens,
        "tokens_fmt": fmt_tokens(tokens) if api else "n/a",
        "model": (api[0].get("model") if api else None),
        "wall_s": round(sum(row.get("duration_ms", 0) or 0 for row in metrics) / 1000.0, 1),
    }


def is_with_arm(stats):
    """An arm is the OneSearch arm if it called `os` or loaded the skill."""
    return bool(stats["os_calls"] or stats["tools"].get("skill") or
                re.search(r"onesearch", stats["question"], re.I))


# -------------------------------------------------------------------- formatting
def fmt_tokens(value):
    """285288 -> '285k', 1555507 -> '1.56M' (the README's own rounding)."""
    if value >= 1_000_000:
        return "%.2fM" % (value / 1_000_000.0)
    return "%dk" % int(value / 1000.0 + 0.5)


def fmt_savings(with_tokens, without_tokens):
    """'~50% fewer tokens' + '2x cheaper' style verdict, as the README states it."""
    if not (with_tokens and without_tokens):
        return None
    saved = 100.0 * (1 - with_tokens / float(without_tokens))
    ratio = without_tokens / float(with_tokens)
    # README style: one decimal below 10x, whole numbers above
    mult = "%.0f" % ratio if ratio >= 10 else "%.1f" % ratio
    return "~%d%% fewer tokens — %s× cheaper" % (round(saved), mult)


def markdown_table(with_stats, without_stats):
    a, b = with_stats, without_stats
    lines = ["| | With OneSearch + skill | Grep / sed only |", "|---|---:|---:|"]
    for label, key in ROWS:
        va, vb = a[key], b[key]
        sa = a["tokens_fmt"] if key == "tokens" else str(va)
        sb = b["tokens_fmt"] if key == "tokens" else str(vb)
        prefix = "~" if key == "tokens" else ""
        # the cheaper/smaller number is the headline: bold the winner of the row
        bold_a, bold_b = va <= vb, vb < va
        cell_a = ("**%s%s**" % (prefix, sa)) if bold_a else ("%s%s" % (prefix, sa))
        cell_b = ("**%s%s**" % (prefix, sb)) if bold_b else ("%s%s" % (prefix, sb))
        lines.append("| %s | %s | %s |" % (label, cell_a, cell_b))
    return "\n".join(lines)


# ---------------------------------------------------------------- README parsing
def readme_expectations(path):
    """Pull the three tables out of README.md: {name: {label: (with, without)}}."""
    if not os.path.exists(path):
        return {}
    text = open(path).read()
    region = re.search(r"## With OneSearch vs without.*?(?=\n## )", text, re.S)
    if not region:
        return {}
    out = {}
    for block in re.finditer(r"<summary><b>(.*?)</b></summary>(.*?)</details>",
                             region.group(0), re.S):
        name = re.split(r"\s+—\s+", block.group(1))[0].strip()
        rows = {}
        for line in block.group(2).splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 3:
                continue
            label = cells[0]
            key = "shell_grabs" if label.startswith("Shell grabs") else \
                  {"Model turns": "turns", "Tool calls": "tool_calls",
                   "Input tokens billed": "tokens"}.get(label)
            if not key:
                continue
            clean = lambda s: s.replace("*", "").replace("~", "").replace(",", "").strip()
            rows[key] = (clean(cells[1]), clean(cells[2]))
        if rows:
            out[name] = rows
    return out


def compare(name, with_stats, without_stats, expected, rows):
    """Append one (name, label, key, arm, computed, readme, ok) tuple per checked cell."""
    for label, key in ROWS:
        exp = expected.get(key)
        if not exp:
            continue
        got = (with_stats["tokens_fmt"] if key == "tokens" else str(with_stats[key]),
               without_stats["tokens_fmt"] if key == "tokens" else str(without_stats[key]))
        for arm, g, e in (("with", got[0], exp[0]), ("without", got[1], exp[1])):
            rows.append((name, label, key, arm, g, e, g == e))


# ------------------------------------------------------------------------- modes
def resolve(path, repos):
    return path if os.path.isabs(path) else os.path.join(repos, path)


def run_report(args):
    expected_all = readme_expectations(README)
    checks = []
    payload = []

    for exp in EXPERIMENTS:
        with_stats = arm_stats(resolve(exp["with_arm"], args.repos))
        without_stats = arm_stats(resolve(exp["without_arm"], args.repos))

        # sanity: the arms are labelled the right way round
        for label, stats, want in (("with", with_stats, True), ("without", without_stats, False)):
            if is_with_arm(stats) != want:
                print("warning: %s arm of %s looks like a %s arm (os calls: %d, skill: %s)"
                      % (label, exp["name"], "OneSearch" if is_with_arm(stats) else "grep-only",
                         stats["os_calls"], stats["tools"].get("skill", 0)), file=sys.stderr)

        payload.append({"name": exp["name"], "with": with_stats, "without": without_stats})

        if args.json:
            continue

        print("%s — %s" % (exp["name"], with_stats["question"] or "(no question)"))
        print("with : %s" % with_stats["session"])
        print("grep : %s" % without_stats["session"])
        verdict = fmt_savings(with_stats["tokens"], without_stats["tokens"])
        print(markdown_table(with_stats, without_stats))
        if verdict:
            print("**Same correct answer for %s.**" % verdict)
        print("detail: bash calls %d -> %d, os calls %d -> %d, tools %s -> %s"
              % (with_stats["bash_calls"], without_stats["bash_calls"],
                 with_stats["os_calls"], without_stats["os_calls"],
                 with_stats["tools"], without_stats["tools"]))
        print()

        compare(exp["name"], with_stats, without_stats,
                expected_all.get(exp["name"], {}), checks)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    if args.no_check:
        return 0
    if not expected_all:
        print("README.md has no comparison tables to check against.")
        return 0

    print("check against README.md")
    bad = 0
    for name, label, key, arm, got, want, ok in checks:
        flag = "ok" if ok else "MISMATCH"
        if not ok:
            bad += 1
        print("  %-9s %-40s %-8s %-8s %-10s %s" % (name, label, arm, got, want, flag))

    missing = [exp["name"] for exp in EXPERIMENTS if exp["name"] not in expected_all]
    for name in missing:
        print("  %-9s %s" % (name, "no table found in README.md"))
    print("\n%d checks, %d mismatched" % (len(checks), bad))
    return 1 if (bad and args.strict) else 0


def run_scan(root):
    """List every arm under a directory tree: useful when starting a new experiment."""
    pattern = os.path.join(os.path.expanduser(root), "*", ".oneloop", "sessions", "*.jsonl")
    for path in sorted(glob.glob(pattern)):
        stats = arm_stats(path)
        print("%-4s %-52s turns=%-3d tools=%-3d grabs=%-3d tokens=%-8s bash=%-3d os=%-2d  %s"
              % ("WITH" if is_with_arm(stats) else "grep",
                 path.replace(os.path.expanduser(root) + os.sep, ""),
                 stats["turns"], stats["tool_calls"], stats["shell_grabs"],
                 stats["tokens_fmt"], stats["bash_calls"], stats["os_calls"],
                 (stats["question"] or "")[:60]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repos", default=DEFAULT_REPOS,
                        help="directory holding the experiment checkouts (default: ~/repos)")
    parser.add_argument("--scan", metavar="DIR",
                        help="just list every OneLoop session under DIR and its metrics")
    parser.add_argument("--json", action="store_true", help="print computed stats as JSON")
    parser.add_argument("--no-check", action="store_true",
                        help="do not compare with README.md")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 when a computed value disagrees with README.md (for CI)")
    args = parser.parse_args(argv)

    if args.scan:
        return run_scan(args.scan)
    return run_report(args)


if __name__ == "__main__":
    sys.exit(main())
