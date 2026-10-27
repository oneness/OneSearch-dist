# OneSearch (trial builds)

Fast semantic code search for coding agents: hybrid lexical + vector retrieval
over a repository, one process, milliseconds per query.

The source is private during the beta. This repo is the public distribution
channel — binaries, the installer, and the agent skill file only. No source
code lives here.

## Install

Binary + `os` shortcut + agent skill, with SHA-256 verification:

```sh
curl -fsSL https://raw.githubusercontent.com/oneness/OneSearch-dist/main/install.sh | bash
```

Pinned to a release:

```sh
curl -fsSL https://raw.githubusercontent.com/oneness/OneSearch-dist/main/install.sh | ONESEARCH_VERSION=v0.1.0 bash
```

Prefer to read it first? Good instinct:

```sh
curl -fsSLO https://raw.githubusercontent.com/oneness/OneSearch-dist/main/install.sh && less install.sh
```

Then:

```sh
cd <a git checkout> && os search "your question about the code"
```

Notes:

- Platforms: Linux x86_64 (glibc 2.35+) and macOS arm64. Need something else?
  [Open an issue.](https://github.com/oneness/OneSearch-dist/issues)
- The first search downloads the embedding model once (~33 MB, cached);
  afterwards a warm query is milliseconds.
- `--repo-dir` must be a Git checkout; it defaults to the current directory.
- `os` is shorthand for `onesearch` and matches the examples in the skill file.
- Session results (`--filter session`) can contain private conversation text —
  review before sharing.

## What agents get

The installer drops `SKILL.md` into the skill dirs it finds
(`~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills`), so agents learn
when to reach for search over grep. The same file is in this repo at
[`skills/onesearch/SKILL.md`](skills/onesearch/SKILL.md) — copy it
project-locally if you prefer:

```sh
cp skills/onesearch/SKILL.md .claude/skills/onesearch/SKILL.md
```

## With OneSearch vs without: same or better answer for a fraction of the tokens

One experiment, three repos: same model, same question, one run per arm — an
agent with `os` and the skill against an agent with only `bash` / `grep` / `sed`.
Open a repo for its numbers.

<details>
<summary><b>VS Code — 15 turns against 20, ~50% fewer tokens</b></summary>

Same repo (VS Code), same model, same question —
*"how is auto-completion coded?"*

One agent used `os` + the skill. The other used only `bash` / `grep` / `sed`.

| | With OneSearch + skill | Grep / sed only |
|---|---:|---:|
| Model turns | **15** | 20 |
| Tool calls | **23** | 33 |
| Shell grabs (`grep`, `sed`, `find`) | **9** | 35 |
| Input tokens billed | **~285k** | ~569k |

**Same correct answer for ~50% fewer tokens.**

And not just cheaper — clearer. Both named the right files with
`file:line` refs. Only the OneSearch answer led with the *why*:

```
provider → registry → SuggestModel → provideSuggestionItems
  → CompletionModel → widget → controller → insert
```

contract → scored registry → trigger state machine → fan-out gather
→ fuzzy rank → render → insert — plus the two design decisions that
explain the code: **first non-empty provider group wins**, and
**incremental refilter** instead of re-scoring everything per keystroke.

</details>

<details>
<summary><b>Medplum — 10 turns against 34, ~88% fewer tokens</b></summary>

Same repo (Medplum), same model, same question —
*"how does workflow work in this repo?"*

One agent used `os` + the skill. The other used only `bash` / `grep` / `sed`.

| | With OneSearch + skill | Grep / sed only |
|---|---:|---:|
| Model turns | **10** | 34 |
| Tool calls | **15** | 52 |
| Shell grabs (`grep`, `sed`, `find`) | **11** | 50 |
| Input tokens billed | **~113k** | ~978k |

**Same correct answer for ~88% fewer tokens — 8.6× cheaper.**

And not just cheaper — both had to open with the same correction, and the
OneSearch answer got there in one move:

```
no `workflow` package → "workflow" is the FHIR pattern:
  PlanDefinition → $apply → CarePlan → RequestGroup → Task
  → Subscriptions → Bots do the dynamics
  → $apply stores `condition` and `relatedAction`, and never runs them
```

</details>

<details>
<summary><b>Vendo — 8 turns against 29, ~92% fewer tokens</b></summary>

Same repo (Vendo), same model, same question —
*"how are customers able to automate their work in this repo?"*

One agent used `os` + the skill. The other used only `bash` / `grep` / `sed`.

| | With OneSearch + skill | Grep / sed only |
|---|---:|---:|
| Model turns | **8** | 29 |
| Tool calls | **20** | 54 |
| Shell grabs (`grep`, `sed`, `find`) | **14** | 37 |
| Input tokens billed | **~130k** | ~1.56M |

**Same correct answer for ~92% fewer tokens — 12× cheaper.**

And not just cheaper — tighter. Both named the same files with `file:line` refs
(28 of them against 59), and both got the whole feature: an automation is a
*record* a customer owns, four authoring doors feed one create, consent is
captured at arming, three trigger kinds feed one atomic tick. Only the OneSearch
answer led with the invariant that explains the rest:

```
four doors (chat tool, make sugar, manifest, .on) → exactly one create
  → arming captures the grant → tick claims a cursor row atomically
  → steps run in-process, goal dispatches to a named runner
```

</details>

### Where these numbers come from

Every figure above is computed from the harness's own logs —
`.oneloop/sessions/*.jsonl` (the conversation) and `.oneloop/metrics/*.jsonl`
(tokens and wall time per API call). [`scripts/experiment_report.py`](scripts/experiment_report.py)
recomputes all three tables and checks them against this file. Stdlib Python
only, no dependencies:

```sh
python3 scripts/experiment_report.py                 # print tables, check this README
python3 scripts/experiment_report.py --strict        # exit 1 on any mismatch (CI)
python3 scripts/experiment_report.py --scan ~/repos   # every OneLoop arm found
```

The mapping is short, and worth knowing if you reproduce a run: **model turns**
are `api_call` events in metrics (not assistant messages — a turn that only
calls tools leaves no text behind), **tool calls** are `ToolCall` messages,
**shell grabs** are bash calls mentioning `grep`, `sed` or `find`, and **input
tokens billed** is the sum of `input_tokens` over API calls — each call bills the
whole context it sends, which is why the grep arm pays again on every turn.

## Uninstall

```sh
rm ~/.local/bin/onesearch ~/.local/bin/os
```

## Feedback

Beta questions, failures, platform requests:
[open an issue](https://github.com/oneness/OneSearch-dist/issues).
