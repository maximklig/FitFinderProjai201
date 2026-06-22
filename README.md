# FitFindr 🛍️

FitFindr is an agent that helps you thrift secondhand clothing and actually do something with what it finds. You describe what you're looking for in plain English (the item, a size, a budget), and it searches a dataset of mock listings, pairs the best find with pieces from your wardrobe, and writes a short caption for the fit. The whole thing runs through one planning loop that calls three tools in succession and passes state between them.

You can run it as a CLI (`python agent.py`) or through the Gradio interface (`python app.py`).

---

## Setup

```bash
pip install -r requirements.txt
```

The two LLM-backed tools use Groq, so you need a key in a `.env` file in the project root (free key at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

`search_listings` runs fully offline and doesn't touch the API, so it works even without a key. Quick sanity check that the data loads:

```bash
python utils/data_loader.py
```

### The data

- `data/listings.json` — 40 mock secondhand listings across tops, bottoms, outerwear, shoes, and accessories. Each listing has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.
- `data/wardrobe_schema.json` — the wardrobe format, plus an `example_wardrobe` (10 items) and an `empty_wardrobe` template for a brand new user.

Both are loaded through helpers in `utils/data_loader.py` (`load_listings()`, `get_example_wardrobe()`, `get_empty_wardrobe()`) so nothing re-reads the files by hand.

---

## Tool Inventory

There are three tools, and they're meant to be called in order — each one builds off what the last one returned.

### Tool 1 — `search_listings`

**Purpose:** Returns the matching listings sorted by relevance given the user's specificities and exact wants. This is the entry point, it's what turns "vintage graphic tee under $30" into actual items the user can pick from.

**Inputs:**
- `description` (`str`) — keywords describing the item and its descriptive tags (e.g. "vintage graphic tee").
- `size` (`str | None`) — the size to filter by, represented by a token like `"M"` or `"L"`. Matching is case-insensitive and `"M"` will match a listing sized `"S/M"` or `"M/L"`. Pass `None` to skip size filtering.
- `max_price` (`float | None`) — the max price the user is willing to pay. Anything above this is dropped before it ever gets scored. Pass `None` to skip price filtering.

**Output:** A `list[dict]` of matching listings sorted best-match first. Each dict carries the name/title of the item, the price, the source (platform), the condition, and the rest of the listing fields. Returns an empty list when nothing matches — it does **not** raise.

**How it works:** it hard-filters on price and size first, then scores whatever's left by keyword overlap with the description (a hit in the title or style tags is worth more than a hit buried in the description), drops anything that scores 0 so you don't get irrelevant junk, and sorts highest score first.

### Tool 2 — `suggest_outfit`

**Purpose:** Does a stylistic evaluation on the back end of which items in the user's wardrobe would best compliment the item they picked. The output can vary every run, but it leans on descriptive tags, stylistic choices, and size to curate something that actually goes together.

**Inputs:**
- `new_item` (`dict`) — the specific clothing item the user wants to style (a listing dict, normally the top result from `search_listings`).
- `wardrobe` (`dict`) — the user's saved wardrobe, a dict with an `items` key holding the list of pieces they own. This highlights the user's style and preferences. May be empty — that's handled.

**Output:** A non-empty `str` describing 1–2 complete outfits that pair the new item with named pieces from the wardrobe, with a quick reason each combination works (color, silhouette, vibe). If the wardrobe is empty it falls back to general styling advice for the item on its own instead of pairing.

### Tool 3 — `create_fit_card`

**Purpose:** Returns 2–4 sentences describing the fit built from `suggest_outfit` and `search_listings` being used in succession. The caption has to feel natural and refrain from sounding like a product placement.

**Inputs:**
- `outfit` (`str`) — the outfit suggestion string returned by `suggest_outfit`.
- `new_item` (`dict`) — the listing dict for the thrifted item (so the caption can name the piece, its price, and where it was found).

**Output:** A `str` of 2–4 sentences usable as an Instagram/TikTok caption. It feeds the outfit combination plus the new item to the LLM and generates a caption about how the clothes work together, the differing factors that make the outfit work, and the mood/vibe. The item name, the platform/source, and the price **must** show up in a natural way, each mentioned only once. If the outfit data is incomplete it returns an error message string instead of raising.

---

## Planning Loop

The loop lives in `agent.py` (`run_agent(query, wardrobe)`) and it follows the flow I drew out in `planning.md`, not some random order.

It starts by parsing the query. If the user asks for a recommendation or says they're looking for something, those keywords tell us they're searching, so relevance is what matters and `search_listings` is where we start. I went with plain regex for the parse instead of asking the LLM to do it, for two reasons — it stays deterministic so the same query always parses the same way, and it doesn't burn an API call (or need the key at all) just to pull out a price and a size. The regex grabs `max_price` off phrases like "under $30" or a bare "$30", grabs `size` off "size M" or a standalone known size token, and whatever's left over becomes the `description` that gets fed to the search.

From there the order is fixed:

1. Parse the query into `description` / `size` / `max_price`.
2. Call `search_listings` with those params. **If it comes back empty, stop here** — set an error and return. The whole point is it should not keep going into `suggest_outfit` with nothing to work with.
3. Pick the top (most relevant) result as the selected item.
4. Feed that plus the wardrobe into `suggest_outfit` and save the string.
5. Feed that outfit string plus the selected item into `create_fit_card` and save the caption.

The loop knows it's done once the fit card is set, or once it bailed early because of an error.

```
User Query (item description, size, budget, wardrobe context)
    │
    ▼
Planning Loop  (regex-parses intent, reads session state after each tool, terminates when fit_card is set)
    │
    ▼
search_listings(description, size, max_price)
    │ returns: matching items (name, price, source, condition), best match first
    ├──[no results]──► set session["error"] → return early
    │
    ▼  session: selected_item = top result
suggest_outfit(new_item, wardrobe)
    │ returns: outfit suggestion string
    ├──[empty wardrobe]──► general styling advice instead of pairing
    │
    ▼  session: outfit_suggestion = "..."
create_fit_card(outfit, new_item)
    │ returns: 2–4 sentence caption (item, source, price each once)
    ├──[incomplete data]──► "Unable to curate a caption..."
    │
    ▼  session: fit_card = "..."
Final Output: top listing + outfit suggestion + fit card
```

---

## State Management

The single source of truth for one interaction is the session dict from `_new_session()`. Nothing gets passed around loose — every tool reads what the last tool wrote into the session and writes its own result back.

The session holds the original query, the parsed params, the search results, the selected item, the wardrobe, the outfit suggestion, the fit card, and an error field. The flow through it is basically the same story as the tools running in order: the listings database is parsed through in tool one, the relevant listings are found and the top one becomes `selected_item`. That selected item's data carries into the second tool (`suggest_outfit`) where the curated outfit gets saved as its own string. Then that outfit string, alongside the selected item, is handed to the third tool (`create_fit_card`) and the caption it generates gets saved too.

So state flows forward purely through the session dict. If the search comes back empty, `error` gets set and the run returns early with `outfit_suggestion` and `fit_card` left as `None` — that's how a caller can tell a happy path from a dead end.

---

## Error Handling

Every tool fails soft. None of them raise on the failure modes below — they return something the agent can actually show the user. The LLM-backed tools also wrap their API call in a try/except so a network blip or a bad key never crashes the agent mid-run.

| Tool | Failure mode | What happens |
|------|--------------|--------------|
| `search_listings` | No results match the query | returns an empty list; the loop catches that, sets an error ("No items found matching your search. Try loosening the size or price...") and stops before `suggest_outfit` |
| `suggest_outfit` | Wardrobe is empty (or has no `items` key) | doesn't crash — falls back to general styling advice for the item on its own |
| `create_fit_card` | Outfit string is missing / empty / whitespace | returns "I am unable to curate a caption based on what was given..." instead of raising |

### A concrete example from testing

The one I care about most is the no-results case, because that's the branch that decides whether the loop keeps going or bails. The test for it (`test_search_empty_results` in `tests/test_tools.py`):

```python
def test_search_empty_results():
    # Nothing is priced at $5 or under, so this should be an empty list, not a crash.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception
```

`"designer ballgown size XXS under $5"` is the deliberate dead-end query — there's nothing in the dataset that cheap, so search returns `[]`. Running the agent on it, `error` comes back set and `outfit_suggestion` / `fit_card` stay `None`, exactly the early-exit I wanted. The full suite (one test per documented failure mode, plus the price/size/relevance filters) is 9 tests and all of them pass:

```
$ python -m pytest tests/ -q
.........                                                                 [100%]
9 passed in 2.52s
```

The two LLM tools are tested on the paths that short-circuit *before* any network call (empty wardrobe, empty outfit), so the whole suite passes offline without a `GROQ_API_KEY`.

---

## Spec Reflection

Looking back at the planning.md spec versus what actually got built, most of it held up but a few things shifted once I was writing real code.

The biggest change is the selection step. In my original architecture I had the user choosing one of the top 3 listings before anything else happened ("the user will choose which of these best suits their need"). When it came to building the loop that turned into the agent just taking the top-ranked result automatically, because a single `run_agent` call goes end to end without stopping to ask. The ranking still does the work — the most relevant item floats to the top — but the human-in-the-loop pick I described didn't survive contact with the implementation. The 3-listings idea still lives in `search_listings` returning a sorted list, it's just that the loop only consumes the first one right now.

The other thing I underspecified was parsing. The spec talks about the agent "breaking apart the sentence" but never said how. I landed on regex for the price and size and treating the leftover as the description, and I think that was the right call for the reasons in the planning loop section — deterministic and free. The tradeoff is it only catches the price/size phrasings I wrote patterns for, so something worded weird could slip past. The wardrobe context part of the spec ("I mostly wear baggy jeans... kept in memory for later") also got simplified — that styling context comes from the structured wardrobe dict now, not from parsing extra detail out of the query.

What matched the spec cleanly: the three tools kept their inputs, outputs and failure modes basically as written, the state-through-a-session-dict approach is exactly what I planned, and the error table maps one-to-one onto the real behavior. If I kept going, the obvious next step would be making the selection interactive in the Gradio app so the user actually gets the pick-one-of-three experience the spec promised.

---

## AI Usage

I used Claude (Claude Code, since it can read the whole repo and not just a snippet I paste in) for the implementation. Two specific instances:

**1 — Implementing the three tools (Milestone 3).**
What I gave it: each tool's spec straight out of `planning.md` (the inputs, the return value, and most importantly the failure mode), plus `listings.json` and `wardrobe_schema.json` so it knew the exact field names to work with, and I pointed it at `utils/data_loader.py` and told it to use `load_listings()` instead of rewriting the file loading.
What it produced: full implementations of `search_listings`, `suggest_outfit`, and `create_fit_card`, including the keyword-scoring logic for search and the Groq calls for the other two.
What I changed/overrode: the first cut of `create_fit_card` was generating near-identical captions on repeated runs, which defeats the point of a fit card. I overrode the temperature, bumping it up (it sits at `1.1` now versus `0.8` on `suggest_outfit`) until the captions actually read fresh each time. I also tightened the search scoring so a keyword hit in the title or style tags weighs more than one buried in the description, since the early version was ranking tangential matches too high. Then I verified against my failure modes — "vintage graphic tee" under 50 returns results, "designer ballgown" XXS under 5 returns an empty list without throwing, and a price filter never returns something over the ceiling.

**2 — Building the planning loop and state (Milestone 4).**
What I gave it: my Architecture diagram and the Planning Loop / State Management sections of `planning.md`, so the code would follow the flow I'd already drawn instead of inventing its own order.
What it produced: `run_agent` wired around the `_new_session` dict, the `_parse_query` regex helper, and the early-exit branch when search comes back empty.
What I changed/overrode: I made the call to keep parsing as deterministic regex rather than letting it route the query through the LLM — I didn't want to spend an API call or need a key just to pull out a price and a size. I also made sure the empty-search branch returns *early* and never falls through into `suggest_outfit`, then verified the two paths by running `agent.py` directly: the happy path ("vintage graphic tee under 30") fills in `selected_item`, `outfit_suggestion` and `fit_card` with `error` staying `None`, and the no-results path ("designer ballgown size XXS under 5") comes back with only `error` set and the other fields left `None`.
