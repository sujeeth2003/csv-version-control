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


