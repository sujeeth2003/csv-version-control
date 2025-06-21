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


def diff_tables(h_old, r_old, h_new, r_new, key=None):
    """Structured diff. Returns dict(columns_added, columns_removed, rows_added, rows_deleted, cells_modified)."""
    d = {"columns_added": [c for c in h_new if c not in h_old], "columns_removed": [c for c in h_old if c not in h_new],
         "rows_added": [], "rows_deleted": [], "cells_modified": []}
    common = [c for c in h_new if c in h_old]

    def as_dict(h, r): return dict(zip(h, r))
    if key:
        for k in key:
            if k not in h_old or k not in h_new:
                raise CsvVcError(f"key column '{k}' missing from a version")
        kf = lambda row: tuple(row[k] for k in key)
        old = {}
        for r in r_old:
            rd = as_dict(h_old, r); kk = kf(rd)
            if kk in old: raise CsvVcError(f"duplicate key {kk} in old version")
            old[kk] = rd
        new = {}
        for r in r_new:
            rd = as_dict(h_new, r); kk = kf(rd)
            if kk in new: raise CsvVcError(f"duplicate key {kk} in new version")
            new[kk] = rd
        for kk, rd in new.items():
            if kk not in old:
                d["rows_added"].append({"key": list(kk), "row": rd})
            else:
                for c in common:
                    if old[kk][c] != rd[c]:
                        d["cells_modified"].append({"key": list(kk), "column": c, "old": old[kk][c], "new": rd[c]})
        for kk, rd in old.items():
            if kk not in new:
                d["rows_deleted"].append({"key": list(kk), "row": rd})
