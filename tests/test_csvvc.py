import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from csvvc.store import CsvVcError, Repo, diff_tables  # noqa: E402


def write(path, text):
    with open(path, "w", newline="") as f:
        f.write(text)


class CsvVcTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, "data.csv")
        self.repo = Repo(self.d); self.repo.init()

    def commit(self, text, msg="m", key=None):
        write(self.f, text)
        return self.repo.commit(self.f, msg, key=key)

    def test_checkout_restores_every_version_exactly(self):
        v = ["id,name\n1,a\n2,b\n", "id,name\n1,a\n2,B\n3,c\n", "id,name,age\n1,a,5\n3,c,6\n"]
        ids = [self.commit(t, f"v{i}", key=["id"])["id"] for i, t in enumerate(v)]
        for i, cid in enumerate(ids):
            out = os.path.join(self.d, f"out{i}.csv")
            self.repo.checkout(cid, out)
            with open(out, newline="") as fh:
                self.assertEqual(fh.read(), v[i])

    def test_row_level_changes_with_key(self):
        self.commit("id,name,city\n1,ann,NYC\n2,bob,LA\n3,cy,SF\n", "base", key=["id"])
        r = self.commit("id,name,city\n1,ann,BOS\n3,cy,SF\n4,di,DC\n", "edit")
        ch = r["changes"]
        self.assertEqual([x["key"] for x in ch["rows_added"]], [["4"]])
        self.assertEqual([x["key"] for x in ch["rows_deleted"]], [["2"]])
        self.assertEqual([(x["key"], x["column"], x["old"], x["new"]) for x in ch["cells_modified"]], [(["1"], "city", "NYC", "BOS")])
        self.assertTrue(all(len(x["cid"]) == 10 for k in ("rows_added", "rows_deleted", "cells_modified") for x in ch[k]))

    def test_reordering_rows_is_not_a_change_when_keyed(self):
        self.commit("id,v\n1,a\n2,b\n", "a", key=["id"])
        r = self.commit("id,v\n2,b\n1,a\n", "reorder")            # different bytes, same data
        ch = r["changes"]
        self.assertEqual((ch["rows_added"], ch["rows_deleted"], ch["cells_modified"]), ([], [], []))

    def test_schema_changes(self):
        self.commit("id,a\n1,x\n", "a", key=["id"])
        r = self.commit("id,b\n1,x\n", "swap column")
        self.assertEqual([c["column"] for c in r["changes"]["columns_added"]], ["b"])
        self.assertEqual([c["column"] for c in r["changes"]["columns_removed"]], ["a"])

    def test_keyless_mode_tracks_added_and_deleted_rows(self):
        self.commit("a,b\n1,2\n3,4\n", "base")
        r = self.commit("a,b\n1,2\n5,6\n", "next")
        self.assertEqual(len(r["changes"]["rows_added"]), 1)
        self.assertEqual(len(r["changes"]["rows_deleted"]), 1)

    def test_identical_commit_refused_and_log_order(self):
        self.commit("a\n1\n", "one")
        with self.assertRaises(CsvVcError): self.commit("a\n1\n", "again")
        self.commit("a\n2\n", "two")
        self.assertEqual([c["message"] for c in self.repo.log()], ["two", "one"])

    def test_diff_between_any_two_versions_and_status(self):
        self.commit("id,v\n1,a\n", "v1", key=["id"])
        self.commit("id,v\n1,b\n", "v2")
        self.commit("id,v\n1,c\n2,z\n", "v3")
        d = self.repo.diff("HEAD~2", "HEAD")
        self.assertEqual(len(d["cells_modified"]), 1); self.assertEqual(len(d["rows_added"]), 1)
        write(self.f, "id,v\n1,c\n2,CHANGED\n")
        st = self.repo.status(self.f)
        self.assertEqual(st["cells_modified"][0]["new"], "CHANGED")

