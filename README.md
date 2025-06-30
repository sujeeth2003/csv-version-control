# csvvc: Git-style version control for CSV files

`git diff` shows a CSV as lines, which is nearly useless: reorder rows and everything changed, add a column and every line changed. `csvvc` versions a CSV the way you think about it: **rows, cells and columns**, each change with a stable **change ID**, and exact restore of any version. Python standard library only.

```bash
python -m csvvc init
python -m csvvc commit prices.csv -m "first import" --key id
python -m csvvc commit prices.csv -m "fix NYC rent"          # key remembered from the previous commit
python -m csvvc log
python -m csvvc diff HEAD~1 HEAD
python -m csvvc show
python -m csvvc status prices.csv                             # what changed since HEAD, before you commit
python -m csvvc checkout HEAD~2 -o old.csv
```
```
diff HEAD~1..HEAD
  ~ row ['1'] .city: 'NYC' -> 'BOS'   [3f9a1c02de]
  + row ['4'] {'id': '4', 'name': 'di', 'city': 'DC'}   [a17b33e90c]
  - row ['2'] {'id': '2', 'name': 'bob', 'city': 'LA'}   [c04d8f6a11]
```

## How it works
- **Snapshots, not replayed diffs.** Every commit stores the full canonical CSV, gzip-compressed and content-addressed by SHA-256 (identical versions are stored once), so `checkout` is exact and a corrupt commit can never poison later ones.
- **Structured change list per commit**, computed against the parent: rows added / deleted, cells modified (old -> new), columns added / removed. Each carries a change ID, `sha1(commit id, kind, row key, column)`.
- **Rows are matched by key column(s)** (`--key id` or `--key a,b`). With a key, **reordering rows is not a change**. Without a key, rows are compared as whole-row multisets, so you only see additions and deletions (an edited row shows as delete + add).
- Commit history is an append-only JSON-lines file (`.csvvc/commits.jsonl`), HEAD is one file: easy to inspect or back up.

## Tests (8 pass)
`python -m unittest discover -s tests`: exact checkout of every historical version (including a schema change), row/cell-level changes with keys, row reordering ignored when keyed, column add/remove, keyless mode, refusing an identical commit, diff between arbitrary versions and `status`, duplicate-key rejection.

## Not (yet) implemented
Branches and merges, remote/push/pull, three-way conflict resolution, rename detection for columns, very large files (the whole table is held in memory), non-UTF-8 encodings.
