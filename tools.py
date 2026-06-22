"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

# Model used for both LLM-backed tools.
_MODEL = "llama-3.3-70b-versatile"

# Words that carry no search signal — stripped out before keyword scoring so
# things like "under" / "size" / a bare price number don't pollute matches.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "with", "for", "to", "of", "in", "on",
    "im", "i", "me", "my", "looking", "look", "want", "need", "find", "show",
    "something", "some", "any", "under", "below", "less", "than", "max",
    "price", "cheap", "size", "sized", "fits", "fit", "wear", "style",
    "thrift", "thrifted", "piece", "item",
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── shared helpers ────────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Lowercase a string and split it into a set of alphanumeric word tokens."""
    return {tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if tok}


def _size_matches(requested: str, listing_size: str) -> bool:
    """
    Case-insensitive size match.

    A requested size matches if it appears as a whole token inside the listing
    size (so "M" matches "S/M" and "M/L" but not "W30 L30"). Listings flagged as
    "one size" / adjustable match any requested size.
    """
    listing_lower = listing_size.lower()
    if "one size" in listing_lower:
        return True
    return requested.strip().lower() in _tokenize(listing_size)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Keywords from the user's description, minus noise words.
    keywords = _tokenize(description) - _STOPWORDS

    scored: list[tuple[int, dict]] = []
    for item in listings:
        # 1. Hard filters — price ceiling and size.
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and not _size_matches(size, item["size"]):
            continue

        # 2. Score by keyword overlap. Each keyword counts once, at the highest
        #    value field it appears in, so broad coverage beats one repeated hit.
        title_toks = _tokenize(item["title"])
        tag_toks = {t for tag in item["style_tags"] for t in _tokenize(tag)}
        cat_toks = _tokenize(item["category"])
        color_toks = {c for col in item["colors"] for c in _tokenize(col)}
        brand_toks = _tokenize(item["brand"] or "")
        desc_toks = _tokenize(item["description"])

        score = 0
        for kw in keywords:
            if kw in title_toks or kw in tag_toks:
                score += 3
            elif kw in cat_toks or kw in color_toks or kw in brand_toks:
                score += 2
            elif kw in desc_toks:
                score += 1

        # 3. Drop anything with no relevant keyword match.
        if score > 0:
            scored.append((score, item))

    # 4. Highest score first; ties keep their original (stable) order.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_line = (
        f"{new_item.get('title', 'this item')} "
        f"(category: {new_item.get('category', 'unknown')}, "
        f"colors: {', '.join(new_item.get('colors', [])) or 'n/a'}, "
        f"style: {', '.join(new_item.get('style_tags', [])) or 'n/a'}, "
        f"size: {new_item.get('size', 'n/a')})"
    )

    items = wardrobe.get("items", []) if wardrobe else []

    if not items:
        # Empty wardrobe — fall back to general styling advice for the item alone.
        prompt = (
            "A thrift shopper is considering buying this second-hand item:\n"
            f"  {item_line}\n\n"
            "They haven't added anything to their wardrobe yet. In 3-5 sentences, "
            "give general styling advice: what kinds of pieces pair well with it, "
            "what aesthetic/vibe it suits, and one or two example outfits they "
            "could build around it. Be specific and practical, not generic."
        )
    else:
        # Format the wardrobe so the model can reference pieces by name.
        wardrobe_lines = []
        for w in items:
            wardrobe_lines.append(
                f"  - {w.get('name', 'unnamed')} "
                f"(category: {w.get('category', 'unknown')}, "
                f"colors: {', '.join(w.get('colors', [])) or 'n/a'}, "
                f"style: {', '.join(w.get('style_tags', [])) or 'n/a'})"
            )
        wardrobe_block = "\n".join(wardrobe_lines)
        prompt = (
            "A thrift shopper is considering buying this second-hand item:\n"
            f"  {item_line}\n\n"
            "Here is what they already own:\n"
            f"{wardrobe_block}\n\n"
            "Suggest 1-2 complete outfits that pair the new item with specific "
            "pieces from their wardrobe. Refer to the wardrobe pieces by name, "
            "explain briefly why each combination works (color, silhouette, "
            "vibe), and keep it to a few sentences per outfit."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a sharp, friendly personal stylist who "
                    "knows thrift and vintage fashion.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001 — never crash the agent on an API error
        return (
            "Sorry, I'm having difficulty pairing clothes from your wardrobe "
            f"right now. Please try again with another item. ({exc})"
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # 1. Guard against missing/empty outfit data — return a message, never raise.
    if not outfit or not outfit.strip():
        return (
            "I am unable to curate a caption based on what was given — "
            "there's no outfit to describe yet. Try styling an item first."
        )

    title = new_item.get("title", "this find")
    price = new_item.get("price")
    price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "a steal"
    platform = new_item.get("platform", "online")

    prompt = (
        "Write a short, shareable social-media caption (2-4 sentences) for an "
        "OOTD-style post about a thrifted outfit.\n\n"
        f"The standout thrifted piece: {title}, found for {price_str} on "
        f"{platform}.\n"
        f"The full outfit it's styled in:\n{outfit.strip()}\n\n"
        "Guidelines:\n"
        "- Sound casual and authentic, like a real person posting their fit — "
        "not a product description or an ad.\n"
        f"- Mention the item ({title}), the price ({price_str}), and the "
        f"platform ({platform}) naturally, each exactly once.\n"
        "- Capture the specific vibe of the outfit.\n"
        "- Return only the caption text, no hashtags-only lines or preamble."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You write punchy, authentic fashion captions for "
                    "Instagram and TikTok.",
                },
                {"role": "user", "content": prompt},
            ],
            # Higher temperature so repeated calls on the same input read fresh.
            temperature=1.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001 — never crash the agent on an API error
        return f"I am unable to curate a caption right now. ({exc})"
