# LocatorBreak schema

## perturbations/*.jsonl (one JSON object per line)

| Field | Type | Meaning |
|---|---|---|
| `app` | string | `supabase-studio`, `grafana` or `portfolio-site` |
| `id` | string | case id, unique within an app (`P0000`...) |
| `target_id` | string | target element id within an app (`T00`...); each target has five cases, one per band |
| `selector_kind` | string | hook used by `brittleSelector`: `id`, `test-id`, `class` |
| `url` | string | page the case was generated on (local URLs for self-hosted apps; the portfolio site is the author's own) |
| `brittleSelector` | string | the CSS selector that the mutation breaks |
| `difficultyBand` | int 1-5 | see README |
| `mutation` | string | band name |
| `groundTruth.tag` / `.text` / `.ariaLabel` | string or null | selector-independent description of the true target. `text` is empty in 15 of 65 Supabase Studio and 50 of 80 Grafana records; `ariaLabel` is null in 60 of 65, 30 of 80, and all 35 portfolio records |
| `groundTruth.role` | null | explicit `role` attribute; null in every record |
| `groundTruth.centroid` / `.box` | object | position and size in CSS pixels at generation time |

## outcomes/outcomes.csv

| Field | Meaning |
|---|---|
| `app`, `case_id`, `target_id`, `band`, `mutation`, `selector_kind` | join keys and case attributes from the perturbation file |
| `resolver` | `brittle-only`, `text-role`, `healenium-3.5.1`, `llm-claude-sonnet-4-6`, `llm-hermes3-8b` |
| `outcome` | `success` (returned the marked true node), `false-heal` (returned a different node), `miss` (returned nothing), `target-missing` (true target absent on the scoring load; excluded) |
| `strategy` | the resolver step that produced the answer: `brittle`, `text-role`, `healenium`, `dom-healer` (Sonnet 4.6), `ollama-dom-healer` (Hermes 3), `dom-healer-none` (the LLM returned no element); empty on `target-missing` rows |
| `heal_ms` | wall-clock time for the resolver call, in milliseconds; empty on the 44 `target-missing` rows |
| `target_text`, `resolved_text` | visible text of the true target and of the returned element; newlines replaced by spaces; may be empty for icon-only elements; two Supabase table names are redacted. Empty in 299 (`target_text`) and 311 (`resolved_text`) of 645 rows |
| `source_file` | the original result file in the companion repository |

## outcomes/coupling_ab.csv

`case_id`, `band`, `variant_A_intent_only`, `variant_B_with_digest`: outcome (8 rows are `target-missing` on both sides, leaving 57 pairs) of the same LLM healer on the same mutated DOM, with the plain intent prompt (A) or the intent plus a digest of the prior clean run (B).

## mined/locator_edits.csv

| Field | Meaning |
|---|---|
| `edit_id` | `E0000`... |
| `repo` | one of the seven repositories in `mined/repos.csv` |
| `commit`, `date` | commit hash and author date |
| `file` | test or selector-registry file that changed |
| `old_kind`, `new_kind` | `testid`, `role`, `text`, `css`, `sel-testid`, `sel-aria` (the last two are entries in Grafana's selector registry). Note that `selector_kind` in Part one spells the same hook `test-id` |
| `old`, `new` | the locator before and after (role locators are written `role|name`) |
| `category` | `class-rename`, `id-testid-rename`, `structure-change`, `attribute-role-change`, `accessible-name-text-change`, `strategy-migration`, `other` |

A row is emitted only when a removed and an added line at the same position in a hunk both contain a locator, the locators differ, and the rest of the statement is identical. CSS strings that are really test-id or text locators (`[data-testid=x]`, `text=Save`) are normalized first, so a pure API rewrite such as `locator('[data-testid=x]')` to `getByTestId('x')` is not counted. Identical edits within one commit are counted once.

## mined/repos.csv

| Field | Meaning |
|---|---|
| `repo` | short name used in `locator_edits.csv` |
| `url` | clone URL |
| `snapshot_commit` | last commit included |
| `mined_paths` | space-separated test directories, double-quoted |
| `since` | first date included |
| `license_note` | free text; consult each repository |

## mined/validation_sample.csv

Up to ten random edits per repository (66 after re-mining, `sample = stratified-10-per-repo`) and 30 random accessible-name edits (`sample = targeted-accessible-name-30`), with a reviewer's judgment (`reviewer_category` is empty when the pair is not the same element): `reviewer_same_target` (Y/N), `reviewer_category`, `agrees` (Y when the pair is the same element and the category is right), and a note.
