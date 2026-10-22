# LocatorBreak

LocatorBreak is a dataset about broken web-UI locators. It has two parts that share one vocabulary of locator changes.

1. **Controlled breaks with an identity oracle.** 180 locator breaks (36 target elements, 5 mutations each) on three public web applications: Supabase Studio, Grafana, and a small personal portfolio site. Each break records a description of the true target element that does not depend on any selector. For the 145 Supabase Studio and Grafana cases, `outcomes.csv` records what five resolvers returned, labeled against the identity oracle as `success`, `false-heal` (a different element was returned) or `miss` (nothing was returned): 645 rows, 601 of them scored. A further 65 rows (57 scored pairs) come from a paired prompt ablation.
2. **Mined locator edits.** 1,187 locator edits mined from the end-to-end test code of seven open-source web applications (Grafana, Supabase, cal.com, Saleor Dashboard, Mattermost, n8n and Element Web) between January 2023 and October 2026, in 526 commits. Each edit is classified by what changed.

Part one was used in Malhotra, *J. Syst. Softw.* (2026), doi:10.1016/j.jss.2026.113157, whose companion repository already held the raw result files. This release adds stable case and target ids, selector kinds, a schema, cleaned and joined tables, the mined corpus, a validation sample, and scripts that regenerate every number in the data paper.

## Layout

| Path | Rows | Contents |
|---|---:|---|
| `perturbations/supabase-studio.jsonl` | 65 | 13 targets x 5 bands |
| `perturbations/grafana.jsonl` | 80 | 16 targets x 5 bands |
| `perturbations/portfolio-site.jsonl` | 35 | 7 targets x 5 bands; generated, not scored |
| `outcomes/outcomes.csv` | 645 | one row per (app, case, resolver) |
| `outcomes/coupling_ab.csv` | 65 | paired prompt ablation on Supabase Studio |
| `mined/locator_edits.csv` | 1,187 | one row per mined locator edit |
| `mined/repos.csv` | 7 | repositories, snapshot commits, mined paths |
| `mined/validation_sample.csv` | 96 | 66 stratified (10 per repository) plus 30 targeted accessible-name edits, checked by hand |
| `scripts/mine_locator_changes.py` | | the miner |
| `scripts/mine_all.sh` | | re-mines every repository in `repos.csv` |
| `scripts/reproduce_tables.py` | | regenerates the paper's numbers (standard library only) |
| `schema.md` | | field definitions |

## Quick start

```bash
python3 scripts/reproduce_tables.py      # Python 3.9+, no dependencies, under a second
bash scripts/mine_all.sh                 # optional: re-mine Part two and compare with the shipped file
```

To regenerate perturbations or re-run the resolvers, use the generator and scorer in `chaos/` of https://github.com/SuneetMalhotra/agent-harness, which also holds the Healenium Docker stack.

## How a case is broken

At scoring time the true node gets a hidden marker attribute. Every case then invalidates the recorded selector by renaming the hook it uses: the id for `#id` selectors, the `data-testid` for test-id selectors, and the class for class selectors. The band adds further change on top:

| Band | Name | Extra change |
|---|---|---|
| 1 | `rename-class` | none (the hook rename only) |
| 2 | `rename-id-testid` | the id or test id is renamed again |
| 3 | `restructure-dom` | the target is wrapped in two extra containers |
| 4 | `retext-sibling` | the text of the target's leaf siblings is replaced; the target's own text is not changed |
| 5 | `attr-reorder-minify` | all attributes except href, type and value are removed and the class is randomized |

Band 1 is named after the generator's original design; for id and test-id selectors it renames the id or test id. The `selector_kind` field records which hook each case uses.

## Known limitations

- All three applications are public and probably in LLM pre-training data.
- Each application was sampled from a single page, so the five cases of a target are not independent. Use `target_id` to group them.
- `groundTruth.role` holds only an explicit `role` attribute and is null in every record. `groundTruth.text` is empty for icon-only controls (50 of 80 Grafana cases).
- The resolvers did not log the returned element's attributes, only its visible text, so a false heal on an unlabeled element cannot be identified from the data.
- On the scoring load some Supabase Studio targets did not render. These rows have outcome `target-missing` and are excluded from rates. The Hermes-3 runs were separate from the other Playwright resolvers, so their missing sets differ slightly.
- Mined edits show which locators the tests used and had to change, not how often each kind of UI change occurs. The miner pairs lines positionally inside a hunk, so some pairs point at different elements. In a stratified hand-checked sample (up to ten per repository, 66 after the final miner fix), 53 edits (80%) were correct; 10 paired different elements and 3 had the wrong category. A further 30 edits from the accessible-name category were checked; across both samples that category was correct in 37 of 41 cases (90%).

## Licence

Data: CC BY 4.0. Scripts: MIT. Mined rows hold only commit hashes, dates, file paths and short locator strings from the listed repositories; see `mined/repos.csv` for each project's licence.

## Citation

See `CITATION.cff`.
