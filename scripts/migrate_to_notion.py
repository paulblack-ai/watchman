#!/usr/bin/env python3
"""Migrate existing Watchman cards from SQLite to Notion database."""

import json
import os
import sqlite3
import sys
import time
import urllib.request

NOTION_TOKEN = os.environ.get("NOTION_TOKEN") or open(
    os.path.join(os.path.dirname(__file__), "..", ".env")
).read().split("NOTION_TOKEN=")[1].split("\n")[0].strip()

NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID") or open(
    os.path.join(os.path.dirname(__file__), "..", ".env")
).read().split("NOTION_DATABASE_ID=")[1].split("\n")[0].strip()

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "watchman.db")
NOTION_URL = "https://api.notion.com/v1/pages"
RATE_LIMIT = 0.5  # seconds between requests (~2/sec)


def get_cards():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, title, source_name, tier, relevance_score, top_dimension,
               review_state, date, url, summary, enrichment_state,
               enrichment_attempt_count, snooze_until
        FROM cards
        WHERE duplicate_of IS NULL
        AND relevance_score IS NOT NULL
        ORDER BY relevance_score DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def build_notion_properties(card):
    props = {
        "Title": {"title": [{"text": {"content": (card["title"] or "Untitled")[:2000]}}]},
        "Source": {"select": {"name": card["source_name"] or "Unknown"}},
        "Tier": {"select": {"name": str(card["tier"])}},
        "Score": {"number": round(card["relevance_score"] / 10, 4) if card["relevance_score"] else 0},
        "URL": {"url": card["url"] or None},
        "Attempts": {"number": card["enrichment_attempt_count"] or 0},
    }
    if card["top_dimension"]:
        props["Top Dimension"] = {"select": {"name": card["top_dimension"]}}
    if card["date"]:
        date_str = card["date"][:10]  # Just YYYY-MM-DD
        if len(date_str) == 10:
            props["Published"] = {"date": {"start": date_str}}
    if card["enrichment_state"]:
        props["Enrichment"] = {"select": {"name": card["enrichment_state"]}}
    if card["snooze_until"]:
        props["Snooze Until"] = {"date": {"start": card["snooze_until"][:10]}}
    return props


def build_body_blocks(card):
    blocks = []
    if card["summary"]:
        # Split summary into chunks of 2000 chars (Notion limit per block)
        text = card["summary"]
        while text:
            chunk = text[:2000]
            text = text[2000:]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })
    return blocks


def create_notion_page(properties, children=None):
    body = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }
    if children:
        body["children"] = children

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        NOTION_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return result.get("id")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ERROR {e.code}: {error_body[:200]}", file=sys.stderr)
        return None


def main():
    cards = get_cards()
    total = len(cards)
    print(f"Migrating {total} cards to Notion...", file=sys.stderr)

    success = 0
    failed = 0

    for i, card in enumerate(cards):
        props = build_notion_properties(card)
        children = build_body_blocks(card)
        page_id = create_notion_page(props, children if children else None)

        if page_id:
            success += 1
        else:
            failed += 1

        if (i + 1) % 50 == 0 or i == total - 1:
            print(
                f"  [{i+1}/{total}] {success} created, {failed} failed",
                file=sys.stderr,
            )

        time.sleep(RATE_LIMIT)

    print(f"\nDone: {success} created, {failed} failed out of {total}", file=sys.stderr)


if __name__ == "__main__":
    main()
