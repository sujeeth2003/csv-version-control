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

