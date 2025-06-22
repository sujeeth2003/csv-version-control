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
    else:
        from collections import Counter
        co, cn = Counter(map(tuple, r_old)), Counter(map(tuple, r_new))
        # without a key we can only compare whole rows (columns must match for this to be meaningful)
        for row, n in (cn - co).items():
            d["rows_added"].extend({"key": None, "row": as_dict(h_new, list(row))} for _ in range(n))
        for row, n in (co - cn).items():
            d["rows_deleted"].extend({"key": None, "row": as_dict(h_old, list(row))} for _ in range(n))
    return d


def _change_ids(commit_id, diff):
    def cid(*parts): return hashlib.sha1("|".join([commit_id, *map(str, parts)]).encode()).hexdigest()[:10]
    diff["columns_added"] = [{"column": c, "cid": cid("coladd", c)} for c in diff["columns_added"]]
    diff["columns_removed"] = [{"column": c, "cid": cid("coldel", c)} for c in diff["columns_removed"]]
    for x in diff["rows_added"]: x["cid"] = cid("add", x["key"] or json.dumps(x["row"], sort_keys=True))
    for x in diff["rows_deleted"]: x["cid"] = cid("del", x["key"] or json.dumps(x["row"], sort_keys=True))
    for x in diff["cells_modified"]: x["cid"] = cid("mod", x["key"], x["column"])
    return diff


class Repo:
    def __init__(self, root="."):
        self.root = os.path.abspath(root)
        self.dir = os.path.join(self.root, DIR)

    # ---------------------------------------------------------------- setup / low-level
    def init(self):
        os.makedirs(os.path.join(self.dir, "objects"), exist_ok=True)
        for f in ("commits.jsonl", "HEAD"):
            open(os.path.join(self.dir, f), "a").close()
        return self.dir

    def _require(self):
        if not os.path.isdir(self.dir):
            raise CsvVcError("not a csvvc repository (run `csvvc init`)")

    def commits(self):
        self._require()
        with open(os.path.join(self.dir, "commits.jsonl")) as f:
            return [json.loads(line) for line in f if line.strip()]

    def head(self):
        with open(os.path.join(self.dir, "HEAD")) as f:
            return f.read().strip() or None

    def resolve(self, ref):
        cs = self.commits()
        if ref in (None, "HEAD"):
            if not cs: raise CsvVcError("no commits yet")
            return next(c for c in cs if c["id"] == self.head())
        if ref.startswith("HEAD~"):
            n = int(ref[5:]); cur = self.resolve("HEAD")
            for _ in range(n):
                if not cur["parent"]: raise CsvVcError("history is not that long")
                cur = next(c for c in cs if c["id"] == cur["parent"])
            return cur
        m = [c for c in cs if c["id"].startswith(ref)]
        if len(m) != 1: raise CsvVcError(f"unknown or ambiguous commit '{ref}'")
        return m[0]

    def _store(self, data):
        sha = hashlib.sha256(data).hexdigest()
        p = os.path.join(self.dir, "objects", sha + ".csv.gz")
        if not os.path.exists(p):
            with gzip.open(p, "wb") as f: f.write(data)
        return sha

    def _load(self, sha):
        with gzip.open(os.path.join(self.dir, "objects", sha + ".csv.gz"), "rb") as f:
            return f.read().decode()

    def table(self, ref):
        return _read_rows(self._load(self.resolve(ref)["snapshot"]), is_text=True)

    # ---------------------------------------------------------------- commands
    def commit(self, csv_path, message, key=None, now=None):
        self._require()
        header, rows = _read_rows(csv_path)
        data = _canonical(header, rows)
        snap = self._store(data)
        cs = self.commits()
        parent = self.head()
        diff = {"columns_added": [], "columns_removed": [], "rows_added": [], "rows_deleted": [], "cells_modified": []}
        if parent:
            p = self.resolve(parent)
            if p["snapshot"] == snap:
                raise CsvVcError("nothing to commit (file identical to HEAD)")
            key = key or p.get("key")
            ph, pr = self.table(parent)
            diff = diff_tables(ph, pr, header, rows, key)
        else:
            diff["rows_added"] = [{"key": None, "row": dict(zip(header, r))} for r in rows] if not key else \
                [{"key": [dict(zip(header, r))[k] for k in key], "row": dict(zip(header, r))} for r in rows]
        ts = now if now is not None else time.time()
        cid = hashlib.sha1(f"{parent}|{snap}|{message}|{ts}".encode()).hexdigest()[:12]
        diff = _change_ids(cid, diff)
        rec = {"id": cid, "parent": parent, "time": ts, "message": message, "snapshot": snap, "key": key,
               "rows": len(rows), "columns": header, "changes": diff}
        with open(os.path.join(self.dir, "commits.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        with open(os.path.join(self.dir, "HEAD"), "w") as f:
            f.write(cid)
        return rec

    def log(self):
        cs = {c["id"]: c for c in self.commits()}
        out, cur = [], self.head()
        while cur:
            out.append(cs[cur]); cur = cs[cur]["parent"]
        return out

    def diff(self, a, b):
        ca, cb = self.resolve(a), self.resolve(b)
        ha, ra = self.table(ca["id"]); hb, rb = self.table(cb["id"])
        return diff_tables(ha, ra, hb, rb, cb.get("key") or ca.get("key"))

    def checkout(self, ref, out_path):
        data = self._load(self.resolve(ref)["snapshot"])
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            f.write(data)
        return out_path

    def status(self, csv_path):
        """Is the working file different from HEAD? Returns the structured diff (empty if identical)."""
        h, r = _read_rows(csv_path)
        ph, pr = self.table("HEAD")
        return diff_tables(ph, pr, h, r, self.resolve("HEAD").get("key"))
