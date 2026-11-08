# Outfit Analyzer

A small terminal tool to find out which outfits from your wardrobe actually work.

It builds every outfit combination possible for today's context (indoors or outdoors, cold / medium / hot), suggests outfits you have never tried, asks you to rate them, and learns which items don't go together. A second script analyses your history: rating distribution, coverage, best and worst items, top outfits.

> The terminal interface is in French.

- Pure Python standard library: no dependencies, no network access, no API keys.
- All data stays in local JSON files.

## Requirements

- Python 3.13+

## Quick start

```bash
git clone <repo-url> outfit-analyzer
cd outfit-analyzer

# 1. Describe your wardrobe (optional: without it, the generic example is used)
cp wardrobe.example.json wardrobe.json
$EDITOR wardrobe.json

# 2. Rate some outfits
python3 outfit_tester.py

# 3. Analyse your history
python3 analysis.py
```

The scripts can be launched from any directory. Data files are always read and written next to the scripts.

## Configuration: `wardrobe.json`

Your wardrobe is personal data. It lives in `wardrobe.json`, which is git-ignored. If that file is missing, `wardrobe.example.json` (committed, generic) is used instead.

| Key | Required | Meaning |
|---|---|---|
| `shirts` | yes | Shirts. Each can be worn alone or over a t-shirt. |
| `t-shirts` | yes | T-shirts. Each can be worn alone or under a shirt. |
| `no_layer_tshirts` | no | T-shirts (also listed in `t-shirts`) too busy to wear under a shirt. |
| `trousers` | yes | Trousers, allowed in every temperature. |
| `shorts` | yes | Shorts, only allowed when hot (may be empty). |
| `shoes` | yes | Shoes, always required. |
| `coats` | yes | Coats, only offered outdoors and when not hot. Always optional. |
| `heavy_coats` | no | Coats (also listed in `coats`) reserved for cold weather. |
| `pull` | yes | Sweaters, offered when cold or medium. Always optional. |

### Combination rules

| Context | Bottoms | Sweater | Coat |
|---|---|---|---|
| Hot (`chaud`) | trousers + shorts | none | none |
| Medium (`medium`) | trousers | optional | outdoors only, no heavy coats, optional |
| Cold (`froid`) | trousers | optional | outdoors only, any coat, optional |

A "top" is either a shirt, a t-shirt, or a `shirt + t-shirt` layer.

## `outfit_tester.py`: rate outfits

1. Answer whether you are going outside and how warm it is.
2. The tool shows how many combinations exist, how many you have already tested and how many remain.
3. It suggests a random untested outfit. Rate it from 1 to 5 (or `q` to quit without saving it).
4. Optionally list the numbers of the items that **don't go together** (e.g. `1,3`).
   - Two or more items flagged → every pair among them becomes an **incompatibility rule**. Any combination containing one of those pairs is excluded, immediately and in future sessions.
   - Flagging a layered top (`shirt + t-shirt`) alone is enough: it creates a rule between the shirt and the t-shirt.
   - A single non-layered item creates no rule.
5. Each rated outfit is saved right away to `historique_outfits.json`.

## `analysis.py`: analyse your history

Filter by indoors/outdoors and temperature, then get:

- number of outfits tested, average / best / worst rating
- number of active incompatibility rules
- rating distribution (bar chart)
- coverage per context: tested outfits still allowed vs. possible combinations
- best and worst item per category (average rating)
- top N outfits. Outfits that a later rule now forbids are flagged with ⚠.

## Data files

| File | Committed | Content |
|---|---|---|
| `wardrobe.example.json` | yes | Generic sample wardrobe |
| `wardrobe.json` | no | Your wardrobe |
| `historique_outfits.json` | no | Your rating history (created automatically) |
| `historique_outfits.corrupt-*.json` | no | Backup of an unreadable history, see below |

### History format

`historique_outfits.json` is a JSON list. Each entry looks like this:

```json
{
  "timestamp": "2026-01-15T08:30:00",
  "context": {"outdoor": true, "temp": "medium"},
  "signature": "blue oxford shirt + white t-shirt|dark denim jeans|brown derbies|-|bomber jacket",
  "outfit": {
    "top": "blue oxford shirt + white t-shirt",
    "bottom": "dark denim jeans",
    "shoes": "brown derbies",
    "pull": null,
    "coat": "bomber jacket"
  },
  "rank": 4,
  "mismatches": [],
  "mismatch_items": []
}
```

### Data safety

- Saves are atomic: the file is written to a temporary file and then renamed, so an interruption never leaves a truncated history.
- If the history is unreadable, it is copied to `historique_outfits.corrupt-<date>.json` before a new one is started.
- Legacy entries using `"cold": true/false` instead of `"temp"` are still read: `true` becomes `froid`, `false` becomes `medium`.

### Renaming or removing items

The history stores item names as text. If you rename an item in `wardrobe.json`, past entries keep the old name. They still count in the statistics, but no longer match current combinations.

## License

[MIT](LICENSE)
