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

## With OneSearch vs without: half the cost, better answer

Same repo (VS Code), same model, same question —
*"how is auto-completion coded?"*

One agent used `os` + the skill. The other used only `bash` / `grep` / `sed`.

| | With OneSearch + skill | Grep / sed only |
|---|---:|---:|
| Model turns | **15** | 20 |
| Tool calls | **23** | 33 |
| Shell grabs (`grep`, `sed`, `find`) | **10** | 30 |
| Input tokens billed | **~285k** | ~569k |

**Same correct answer for ~50% of the tokens.**

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

Why it happens: the skill asks twice — definition + behavior in one
`batch` pass — then reads only the hit ranges. Without it the agent
walks the tree and pastes whole files, paying for every line on every
later turn.

```sh
printf '%s\n' \
  "where is the completion provider interface declared and registered" \
  "what happens when a completion is triggered" | os batch
```

## Uninstall

```sh
rm ~/.local/bin/onesearch ~/.local/bin/os
```

## Feedback

Beta questions, failures, platform requests:
[open an issue](https://github.com/oneness/OneSearch-dist/issues).
