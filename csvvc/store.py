"""Git-style version control for CSV files, with ROW-LEVEL change tracking.

Git diffs CSVs as lines, which is useless when a row moves or a column is added. Here each commit stores
  * a compressed, content-addressed snapshot of the whole file (so `checkout` is exact and never depends on replaying diffs)
  * a structured change list against the parent commit: added rows, deleted rows, modified cells, added/removed columns,
    each with a stable CHANGE ID = sha1(commit id, kind, row key, column)
Rows are matched by a key column (or several) when given, otherwise by full-row content (then rows can only be added/deleted).

Layout:  .csvvc/objects/<sha256>.csv.gz   .csvvc/commits.jsonl   .csvvc/HEAD
"""
import csv
import gzip
import hashlib
import io
import json
import os
import time

DIR = ".csvvc"


class CsvVcError(Exception):
    pass


def _read_rows(path_or_text, is_text=False):
    f = io.StringIO(path_or_text) if is_text else open(path_or_text, newline="", encoding="utf-8")
    with f:
        rows = list(csv.reader(f))
    if not rows:
        raise CsvVcError("empty CSV")
    return rows[0], rows[1:]


def _canonical(header, rows):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return out.getvalue().encode()


