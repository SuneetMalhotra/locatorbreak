#!/usr/bin/env bash
# Re-mine every repository in mined/repos.csv, rebuild the edit table, and compare it with
# the shipped mined/locator_edits.csv. Needs git and python3; takes tens of minutes.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd); WORK=${WORK:-$PWD/_mining}; mkdir -p "$WORK"
tail -n +2 "$HERE/mined/repos.csv" | while IFS=, read -r repo url sha paths since _; do
  paths=${paths//\"/}
  [ -d "$WORK/$repo" ] || git clone -q --filter=blob:none --no-checkout "$url" "$WORK/$repo" </dev/null
  git -C "$WORK/$repo" fetch -q origin "$sha" </dev/null || true
  # shellcheck disable=SC2086
  git -C "$WORK/$repo" log "$sha" --since="$since" --format='@@COMMIT %H %ad' --date=short -p --unified=0 -- $paths \
    > "$WORK/$repo.patch" </dev/null
  python3 -I "$HERE/scripts/mine_locator_changes.py" "$repo" "$WORK/$repo.patch" "$WORK/$repo.csv" </dev/null
done
python3 -I - "$WORK" "$HERE" <<'PY'
import csv, sys, pathlib
work, here = map(pathlib.Path, sys.argv[1:3])
repos = [r["repo"] for r in csv.DictReader((here / "mined/repos.csv").open())]
rows = []
for repo in repos:
    rows += list(csv.DictReader((work / f"{repo}.csv").open()))
fields = ["edit_id", "repo", "commit", "date", "file", "old_kind", "old", "new_kind", "new", "category"]
out = work / "locator_edits_rebuilt.csv"
with out.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
    for i, r in enumerate(rows):
        r["edit_id"] = f"E{i:04d}"; w.writerow({k: r[k] for k in fields})
key = lambda r: tuple(r[k] for k in fields[1:])
shipped = [key(r) for r in csv.DictReader((here / "mined/locator_edits.csv").open())]
rebuilt = [key(r) for r in csv.DictReader(out.open())]
print(f"rebuilt {len(rebuilt)} edits -> {out}")
print("MATCHES shipped file" if rebuilt == shipped else "DIFFERS from shipped file (upstream history or miner changed)")
PY
