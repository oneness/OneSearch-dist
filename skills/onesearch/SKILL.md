---
name: onesearch
description: Semantic code and session search over the current repo. Use before grepping when exploring unfamiliar code or asking how something behaves.
---

# OneSearch

Semantic retrieval over the current repository (and its OneLoop session logs).
One process, a warm index, milliseconds per query.

## Reach for it first

Unfamiliar code, no context, or a question about behavior rather than a name:
invoke OneSearch **before** grepping, listing, or guessing at paths. Treat the
answer as a pointer into the codebase — a librarian giving you a section range,
not the book itself.

Phrase the query the way the code would: **name the resource, operation or
symbol, and the verb it performs.** Naming the thing beats repeating the
user's own words.

Keep the user's phrasing only for genuine prose questions — "why was this
designed this way" — and pair it with `--filter docs`. For anything about
behavior, name the code.

**Ask twice — two aspects, not two phrasings.** Turn the question into two
queries that reach its core from different sides — most often the definition
and the behaviour ("what declares and constrains X" and "what happens to X
when Y runs"), or the read path and the write path. Two aspects of one
question, not a rewording of one phrase: a paraphrase mostly returns the
chunks you already had. `batch` runs both in one pass, for one tool call.

```sh
printf '%s\n' \
  "where <subject> is declared, configured and validated" \
  "what happens to <subject> when <event> runs" | os batch
```

Skip the second query when the first already names the thing precisely and the
index confirms it.

## Setup

If `os` is not on PATH, install it (binary + this skill):

```sh
curl -fsSL https://oneness.github.io/OneSearch/install.sh | bash
```

`os` is shorthand for `onesearch`. `--repo-dir` must be a Git checkout and
defaults to the current directory. The first search downloads the embedding
model once (~33 MB, cached); afterwards a warm query is milliseconds.

## Filter

Omit it unless the question is not about source code. The default is `code`.

| value | contents | use |
|---|---|---|
| `code` | repository source files | **the default**; every question about behavior |
| `docs` | documentation, prose, notes | "where is this documented", design rationale |
| `config` | build, package and data files | settings, manifests, CI |
| `session` | OneLoop conversation logs | only when the user asks about past sessions |
| `all` | everything | rarely; docs and logs then rank against the code |

Documentation and configuration repeat a question's vocabulary and win on words
alone, so they are searched only when asked for. If a conceptual question
returns nothing useful in code, try `--filter docs` before giving up.
`--filter` is global, so it may come before or after the subcommand.

## search or related

- **`search`** — nothing pinned down yet. Describe the behavior, get candidate
  ranges back.
- **`related FILE:LINE`** (alias `rel`) — one chunk is already right and you
  want its neighbours: sibling implementations, callers, tests, the rest of an
  interface. It compares the seed chunk's own text by similarity and stays
  inside the seed's language. Defaults to `-k 5`.

## Reading the results

1. **The index above the previews is the map.** Read all of it before any
   preview: it names every hit's file, range and first declaration. Previews are
   for the one hit you chose, not for browsing.
2. **Read the printed range, not the file.** `path:start-end` is the answer's
   neighbourhood; jumping to a whole-file read is the expensive failure mode.
3. Ranks are reading order, not probability. `--explain` prints semantic and
   lexical ranks with every score multiplier, `--json` for structure, `--timing`
   for cost.
4. **Open before searching again.** After a search, read one returned range
   before issuing another search or a grep. A grep is justified only by a
   literal you already hold; rewriting a hit into a grep throws away the ranking
   you just paid for.
5. If the top chunks are wrong, requery with the vocabulary the results actually
   used. The index holds the code's words, and their words are often not the
   user's.

## Command shape

The first argument is always a subcommand — `search`, `related`, `batch` (one
query per stdin line, loading the model and index once), `index`, `clear` — so
a query that happens to be a command word is still searchable. `search`
reindexes a stale snapshot by itself.

```sh
os search "how are sessions persisted"
os search "how is the retry policy designed" --filter docs
printf 'first phrasing\nsecond phrasing\n' | os batch
os related src/session.ts:120-160 -k 5
os --repo-dir ~/other/checkout --session-dir ~/logs search "retry logic"
```

`-k` caps output (10 for `search`, 5 for `related`), and each hit is one line of
index plus its code, so `-k 20` is a lot of lines: pipe through `head` only
knowingly.

`index` builds or refreshes the snapshot and prints its size; `clear` deletes
it (safe — the next search rebuilds). Session results can contain private
conversation text — review before sharing.
