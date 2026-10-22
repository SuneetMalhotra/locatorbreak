#!/usr/bin/env python3
"""Mine locator edits from end-to-end test histories (git log -p --unified=0 output).

A *locator edit* is a hunk line pair (removed, added) in an E2E test or selector
file where both lines contain a locator expression and the locator differs.
Each edit is classified into the mutation families of the LocatorBreak bands.

Usage: mine_locator_changes.py <repo-name> <patch-file> <out.csv>
"""
import csv, re, sys

REPO, PATCH, OUT = sys.argv[1:4]

# --- locator extraction -------------------------------------------------------
Q = r"""(['"`])((?:\\.|(?!\1).)*)\1"""
PATTERNS = [
    ("testid", re.compile(r"getByTestId\(\s*" + Q)),
    ("role",   re.compile(r"getByRole\(\s*" + Q + r"\s*(?:,\s*\{[^}]*name:\s*" + Q + r")?")),
    ("text",   re.compile(r"getBy(?:Text|Label|Placeholder|Title|AltText)\(\s*" + Q)),
    ("text",   re.compile(r"cy\.contains\(\s*" + Q)),
    ("css",    re.compile(r"(?:\.locator|\$\$?|cy\.get|\.find|page\.(?:click|fill|waitForSelector|hover|check))\(\s*" + Q)),
]
SELECTOR_FILE = re.compile(r"grafana-e2e-selectors/src/.*\.ts$")
SEL_ENTRY = re.compile(r"^\s*[\w$]+\s*:\s*(?:\(.*?\)\s*=>\s*)?" + Q)


PURE_TESTID = re.compile(r"""^[a-z]*\[?data-(?:testid|test-id|test|cy|qa)\s*=\s*["']?([^"'\]]+)["']?\]?$""")
PW_TEXT = re.compile(r"""^text\s*=\s*["']?(.+?)["']?$|:(?:has-)?text\(\s*["'](.+?)["']\s*\)""")


def normalize_css(sel):
    """Map CSS-engine strings that are really test-id or text locators onto those kinds,
    so a pure API rewrite (e.g. '[data-testid=x]' -> getByTestId('x')) is not counted as an edit."""
    m = PURE_TESTID.match(sel.strip())
    if m:
        return ("testid", m.group(1))
    m = PW_TEXT.search(sel.strip())
    if m and (sel.strip().startswith("text") or sel.strip().startswith(":")):
        return ("text", m.group(1) or m.group(2))
    return None


TESTID_LIKE = re.compile(r"^[a-z0-9]+(?:[-_][a-zA-Z0-9]+)+$")


def locators(line, path):
    found = []
    for kind, rx in PATTERNS:
        for m in rx.finditer(line):
            if kind == "text" and TESTID_LIKE.match(m.group(2) or ""):
                found.append(("testid", m.group(2)))
            elif kind == "css" and normalize_css(m.group(2)):
                found.append(normalize_css(m.group(2)))
            elif kind == "role":
                found.append((kind, f"{m.group(2)}|{m.group(4) or ''}"))
            else:
                found.append((kind, m.group(2)))
    if not found and SELECTOR_FILE.search(path):
        m = SEL_ENTRY.match(line)
        if m:
            v = m.group(2)
            found.append(("sel-testid" if v.startswith("data-testid") else "sel-aria", v))
    return found


# --- classification -----------------------------------------------------------
CLASS_TOK = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")
ID_TOK = re.compile(r"#([\w-]+)|data-(?:testid|test-id|test|cy|qa|e2e)[=~^$*]*[\"']?([^\"'\]]+)|\[id=[\"']?([^\"'\]]+)")
ATTR_TOK = re.compile(r"\[([\w:-]+)")
STRUCT = re.compile(r">|:nth-|nth\(|\.first\(|\.last\(|:has\(|\s+[a-z]+\s*$|//|\.\.")


def shape(sel):
    t = re.sub(r"\[[^\]]*\]", "[]", sel)
    t = re.sub(r"\([^)]*\)", "()", t)
    parts = [p for p in re.split(r"\s*>\s*|\s+", t.strip()) if p]
    return (len(parts), ">" in t, ":nth" in t)


def css_kind(sel):
    if ID_TOK.search(sel):
        return "id"
    if "aria-" in sel or re.search(r"\[(?!data-(?:testid|test-id|test|cy|qa|e2e))[\w:-]+", sel):
        return "attr"
    if CLASS_TOK.search(sel):
        return "class"
    return "tag"


def classify(k_old, v_old, k_new, v_new):
    norm = lambda k: {"sel-testid": "testid", "sel-aria": "text"}.get(k, k)
    ko, kn = norm(k_old), norm(k_new)
    if ko != kn:
        return "strategy-migration"            # e.g. CSS -> getByRole
    if ko == "testid":
        return "id-testid-rename"
    if ko == "text":
        return "accessible-name-text-change" if k_old != "sel-aria" else "attribute-role-change"
    if ko == "role":
        r_o, n_o = v_old.split("|", 1)
        r_n, n_n = v_new.split("|", 1)
        return "attribute-role-change" if r_o != r_n else "accessible-name-text-change"
    # css
    co, cn = css_kind(v_old), css_kind(v_new)
    if shape(v_old) != shape(v_new):
        return "structure-change"
    if co != cn:                           # CSS to CSS of another kind: classify by the new hook
        return {"class": "class-rename", "id": "id-testid-rename"}.get(cn, "attribute-role-change")
    return {"class": "class-rename", "id": "id-testid-rename",
            "attr": "attribute-role-change"}.get(co, "other")


def remainder(line, locs):
    t = line
    for _, v in locs:
        for part in v.split("|"):
            if part:
                t = t.replace(part, "")
    t = re.sub(r"getBy\w+|locator|cy\.get|cy\.contains|\$\$?", "LOC", t)
    t = re.sub(r"\{\s*name:\s*['\"`]{2}\s*\}|,\s*\{[^}]*\}", "", t)
    t = re.sub(r"['\"`]", "", t)
    return re.sub(r"\s+", "", t)


# --- patch walk ----------------------------------------------------------------
rows, commit, date, path = [], None, None, None
removed, added = [], []


def flush():
    global removed, added
    pairs = min(len(removed), len(added))
    for (lo, ln) in zip(removed[:pairs], added[:pairs]):
        lo_l, ln_l = locators(lo, path), locators(ln, path)
        if not lo_l or not ln_l:
            continue
        if remainder(lo, lo_l) != remainder(ln, ln_l):
            continue                      # different statement: not the same target
        for (ko, vo), (kn, vn) in zip(lo_l, ln_l):
            if vo == vn and ko == kn:
                continue
            if vo.strip() == vn.strip() or vo.replace("!", "") == vn.replace("!", ""):
                continue                  # whitespace or TypeScript non-null edits only
            rows.append(dict(repo=REPO, commit=commit, date=date, file=path,
                             old_kind=ko, old=vo[:200], new_kind=kn, new=vn[:200],
                             category=classify(ko, vo, kn, vn)))
    removed, added = [], []


TEST_PATH = re.compile(r"(e2e|playwright|cypress|\.spec\.|\.test\.|grafana-e2e-selectors)")
with open(PATCH, encoding="utf-8", errors="replace") as fh:
    for line in fh:
        if line.startswith("@@COMMIT "):
            flush(); _, commit, date = line.split()[:3]; path = None
        elif line.startswith("+++ "):
            flush(); p = line[4:].strip(); path = p[2:] if p.startswith("b/") else p
            if not TEST_PATH.search(path or ""):
                path = None
        elif line.startswith("@@"):
            flush()
        elif path and line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
        elif path and line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    flush()

# de-duplicate identical (old,new) edits within a commit (mass renames)
seen, uniq = set(), []
for r in rows:
    key = (r["commit"], r["old"], r["new"])
    if key not in seen:
        seen.add(key); uniq.append(r)

with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(uniq[0].keys()))
    w.writeheader(); w.writerows(uniq)
print(f"{REPO}: {len(uniq)} locator edits ({len(rows)} before de-dup) "
      f"in {len({r['commit'] for r in uniq})} commits")
