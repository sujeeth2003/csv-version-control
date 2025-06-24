"""csvvc command line:  init | commit | log | diff | checkout | status | show"""
import argparse
import sys
import time

from .store import CsvVcError, Repo


def fmt_diff(d):
    lines = []
    for c in d["columns_added"]:   lines.append(f"  + column {c['column'] if isinstance(c, dict) else c}")
    for c in d["columns_removed"]: lines.append(f"  - column {c['column'] if isinstance(c, dict) else c}")
    for x in d["rows_added"]:      lines.append(f"  + row {x['key'] or ''} {x['row']}" + (f"   [{x['cid']}]" if "cid" in x else ""))
    for x in d["rows_deleted"]:    lines.append(f"  - row {x['key'] or ''} {x['row']}" + (f"   [{x['cid']}]" if "cid" in x else ""))
    for x in d["cells_modified"]:  lines.append(f"  ~ row {x['key']} .{x['column']}: {x['old']!r} -> {x['new']!r}" + (f"   [{x['cid']}]" if "cid" in x else ""))
    return "\n".join(lines) or "  (no changes)"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="csvvc", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    c = sub.add_parser("commit"); c.add_argument("file"); c.add_argument("-m", "--message", required=True)
    c.add_argument("--key", help="comma-separated key column(s) identifying a row")
    sub.add_parser("log")
    d = sub.add_parser("diff"); d.add_argument("a", nargs="?", default="HEAD~1"); d.add_argument("b", nargs="?", default="HEAD")
    o = sub.add_parser("checkout"); o.add_argument("ref"); o.add_argument("-o", "--output", required=True)
    s = sub.add_parser("status"); s.add_argument("file")
    sh = sub.add_parser("show"); sh.add_argument("ref", nargs="?", default="HEAD")
    a = ap.parse_args(argv)
    repo = Repo(".")
    try:
        if a.cmd == "init":
            print(f"initialized empty csvvc repository in {repo.init()}")
        elif a.cmd == "commit":
            r = repo.commit(a.file, a.message, key=a.key.split(",") if a.key else None)
            ch = r["changes"]
            print(f"[{r['id']}] {a.message}\n  {r['rows']} rows, "
                  f"+{len(ch['rows_added'])} rows, -{len(ch['rows_deleted'])} rows, ~{len(ch['cells_modified'])} cells")
        elif a.cmd == "log":
            for cm in repo.log():
                ch = cm["changes"]
                print(f"commit {cm['id']}  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cm['time']))}\n"
                      f"    {cm['message']}\n    (+{len(ch['rows_added'])} rows, -{len(ch['rows_deleted'])} rows, ~{len(ch['cells_modified'])} cells)")
        elif a.cmd == "diff":
            print(f"diff {a.a}..{a.b}\n{fmt_diff(repo.diff(a.a, a.b))}")
        elif a.cmd == "checkout":
            print(f"wrote {repo.checkout(a.ref, a.output)}")
        elif a.cmd == "status":
            print(fmt_diff(repo.status(a.file)))
