#!/usr/bin/env python3
"""Regenerate every number in the LocatorBreak data paper from the released CSV/JSONL files.
Standard library only.  Usage: python3 scripts/reproduce_tables.py"""
import csv, json, collections, pathlib
from decimal import Decimal, ROUND_HALF_UP

def r2(x):
    """Round half up to two places, as in the paper."""
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
ROOT = pathlib.Path(__file__).resolve().parents[1]

pert = collections.Counter()
for f in sorted((ROOT / "perturbations").glob("*.jsonl")):
    for line in f.open():
        p = json.loads(line); pert[(p["app"], p["difficultyBand"])] += 1
print("Perturbations by app:", {a: sum(v for (b, _), v in pert.items() if b == a) for a in sorted({a for a, _ in pert})})

rows = list(csv.DictReader((ROOT / "outcomes/outcomes.csv").open()))
print(f"\nTable 1: resolver outcomes ({len(rows)} rows; scored = success + false-heal + miss)")
grp = collections.defaultdict(collections.Counter)
for r in rows:
    grp[(r["app"], r["resolver"])][r["outcome"]] += 1
for (app, res), c in sorted(grp.items()):
    n = c["success"] + c["false-heal"] + c["miss"]
    print(f"  {app:16s} {res:24s} N={n:3d}  success={r2(c['success']/n)}  false-heal={r2(c['false-heal']/n)}  miss={r2(c['miss']/n)}  target-missing={c['target-missing']}")

ab = list(csv.DictReader((ROOT / "outcomes/coupling_ab.csv").open()))
both = [r for r in ab if r["variant_A_intent_only"] in ("success", "false-heal", "miss") and r["variant_B_with_digest"] in ("success", "false-heal", "miss")]
print(f"\nCoupling A/B: {len(ab)} rows, {len(both)} paired")

ed = list(csv.DictReader((ROOT / "mined/locator_edits.csv").open()))
print(f"\nTable 2: mined locator edits ({len(ed)} edits, {len({e['commit'] for e in ed})} commits)")
for repo in sorted({e["repo"] for e in ed}):
    xs = [e for e in ed if e["repo"] == repo]
    c = collections.Counter(e["category"] for e in xs)
    print(f"  {repo}: n={len(xs)} commits={len({e['commit'] for e in xs})} files={len({e['file'] for e in xs})} "
          f"span={min(e['date'] for e in xs)}..{max(e['date'] for e in xs)}")
    for k, v in c.most_common():
        print(f"     {k:30s} {v:4d} ({100*v/len(xs):.0f}%)")
c = collections.Counter(e["category"] for e in ed)
print("  ALL:", len(ed), "edits;", {k: f"{v} ({100*v/len(ed):.0f}%)" for k, v in c.most_common()})
cc = collections.Counter()
for (repo, commit, cat) in {(e["repo"], e["commit"], e["category"]) for e in ed}:
    cc[cat] += 1
print("  commits containing each category:", dict(cc.most_common()))
val = list(csv.DictReader((ROOT / "mined/validation_sample.csv").open()))
print(f"  validation (all reviewed rows): {sum(v['agrees']=='Y' for v in val)}/{len(val)} agree; "
      f"different target {sum(v['reviewer_same_target']=='N' for v in val)}; "
      f"wrong category {sum(v['reviewer_same_target']=='Y' and v['agrees']=='N' for v in val)}")
st = [v for v in val if v["sample"].startswith("strat")]
nm = [v for v in val if v["category"] == "accessible-name-text-change"]
print(f"  stratified sample: {sum(v['agrees']=='Y' for v in st)}/{len(st)}; accessible-name precision (both samples): {sum(v['agrees']=='Y' for v in nm)}/{len(nm)}")
mig = collections.Counter((e["old_kind"], e["new_kind"]) for e in ed if e["category"] == "strategy-migration")
print("  top strategy migrations:", mig.most_common(6))
print("  migration targets (new kind):", collections.Counter(e["new_kind"] for e in ed if e["category"] == "strategy-migration"))
fh = [r for r in rows if r["outcome"] == "false-heal"]
lab = [r for r in fh if r["target_text"].strip()]
print(f"\nFalse heals: {len(fh)}; target has no visible text: {len(fh)-len(lab)}; labelled target: {len(lab)}, "
      f"of which same non-empty text returned: {sum(r['resolved_text']==r['target_text'] for r in lab)}")
bs = [r for r in fh if r["resolver"] == "brittle-only"]
print(f"Broken selector returns a wrong element: {len(bs)} ({sum(r['selector_kind']=='class' for r in bs)} class selectors)")
scored = collections.defaultdict(set)
for r in rows:
    if r["app"] == "supabase-studio" and r["outcome"] in ("success", "false-heal", "miss"):
        scored[r["resolver"]].add(r["case_id"])
common = set.intersection(*(scored[k] for k in ("brittle-only", "text-role", "llm-claude-sonnet-4-6", "healenium-3.5.1")))
h = collections.Counter(r["outcome"] for r in rows if r["resolver"] == "healenium-3.5.1" and r["case_id"] in common and r["selector_kind"] == "id")
print(f"Healenium on id cases of the {len(common)}-case common Supabase set: {dict(h)}")
hk = collections.defaultdict(collections.Counter)
for r in rows:
    if r["resolver"] == "healenium-3.5.1" and r["outcome"] in ("success", "false-heal", "miss"):
        hk[r["selector_kind"]][r["outcome"]] += 1
print("Healenium by selector kind (all scored):", {k: dict(v) for k, v in hk.items()})
print("\nSuccess by target label (scored rows):")
g = collections.defaultdict(collections.Counter)
for r in rows:
    if r["outcome"] in ("success", "false-heal", "miss"):
        g[(r["resolver"], "no visible text" if not r["target_text"].strip() else "visible text")][r["outcome"]] += 1
for k, v in sorted(g.items()):
    n = sum(v.values()); print(f"  {k[0]:24s} {k[1]:16s} {v['success']}/{n} = {v['success']/n:.2f}")
print("\nSuccess by band (scored rows, both apps):")
b = collections.defaultdict(collections.Counter)
for r in rows:
    if r["outcome"] in ("success", "false-heal", "miss"):
        b[(r["resolver"], r["band"])][r["outcome"]] += 1
for res in sorted({k[0] for k in b}):
    print(f"  {res:24s}", "  ".join(f"b{x}:{b[(res,x)]['success']}/{sum(b[(res,x)].values())}" for x in "12345"))
