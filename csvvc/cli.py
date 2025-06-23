"""csvvc command line:  init | commit | log | diff | checkout | status | show"""
import argparse
import sys
import time

from .store import CsvVcError, Repo


