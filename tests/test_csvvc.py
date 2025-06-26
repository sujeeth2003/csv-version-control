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

