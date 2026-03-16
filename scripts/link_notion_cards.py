#!/usr/bin/env python3
"""Link Notion pages back to SQLite cards and set default Review Status."""

import json
import os
import sqlite3
import sys
import time
import urllib.request

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path) as f:
        for line in f:
            if line.startswith("NOTION_TOKEN="):
                NOTION_TOKEN = NOTION_TOKEN or line.split("=", 1)[1].strip()
            if line.startswith("NOTION_DATABASE_ID="):
                NOTION_DATABASE_ID = NOTION_DATABASE_ID or line.split("=", 1)[1].strip()

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "watchman.db")
NOTION_URL = "https://api.notion.com/v1"
RATE_LIMIT = 0.35


def notion_request(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(
        f"{NOTION_URL}/{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        method=method,
    )
    time.sleep(RATE_LIMIT)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def query_all_notion_pages():
    """Paginate through all Notion database pages."""
    pages = []
    start_cursor = None
    while True:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        result = notion_request("POST", f"databases/{NOTION_DATABASE_ID}/query", body)
        pages.extend(result.get("results", []))
        print(f"  Fetched {len(pages)} pages...", file=sys.stderr)
        if not result.get("has_more"):
            break
        start_cursor = result.get("next_cursor")
    return pages


def main():
    conn = sqlite3.connect(DB_PATH)

    # Step 1: Add notion_page_id column if missing
    columns = [row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()]
    if "notion_page_id" not in columns:
        conn.execute("ALTER TABLE cards ADD COLUMN notion_page_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_notion_page_id ON cards(notion_page_id)")
        conn.commit()
        print("Added notion_page_id column to cards table", file=sys.stderr)
    else:
        print("notion_page_id column already exists", file=sys.stderr)

    # Step 2: Build URL → card_id map from SQLite
    url_to_card = {}
    for row in conn.execute("SELECT id, url FROM cards WHERE duplicate_of IS NULL"):
        url_to_card[row[1]] = row[0]
    print(f"SQLite: {len(url_to_card)} cards with URLs", file=sys.stderr)

    # Step 3: Fetch all Notion pages
    print("Fetching Notion pages...", file=sys.stderr)
    pages = query_all_notion_pages()
    print(f"Notion: {len(pages)} pages", file=sys.stderr)

    # Step 4: Link and set defaults
    linked = 0
    defaulted = 0
    batch_updates = []

    for page in pages:
        page_id = page["id"]
        props = page.get("properties", {})

        # Extract URL from Notion page
        url_prop = props.get("URL", {})
        notion_url = url_prop.get("url")

        # Link to SQLite by matching URL
        if notion_url and notion_url in url_to_card:
            card_id = url_to_card[notion_url]
            conn.execute(
                "UPDATE cards SET notion_page_id = ? WHERE id = ?",
                (page_id, card_id),
            )
            linked += 1

        # Check Review Status
        review_prop = props.get("Review Status", {})
        review_select = review_prop.get("select")
        if not review_select:
            # No Review Status set — queue for "To Review" update
            batch_updates.append(page_id)

    conn.commit()
    print(f"Linked {linked} Notion pages to SQLite cards", file=sys.stderr)

    # Step 5: Batch update Review Status to "To Review"
    print(f"Setting Review Status to 'To Review' on {len(batch_updates)} pages...", file=sys.stderr)
    for i, page_id in enumerate(batch_updates):
        try:
            notion_request("PATCH", f"pages/{page_id}", {
                "properties": {
                    "Review Status": {"select": {"name": "To Review"}}
                }
            })
            defaulted += 1
        except Exception as e:
            print(f"  Failed to update {page_id}: {e}", file=sys.stderr)

        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(batch_updates)}] updated", file=sys.stderr)

    print(f"\nDone: {linked} linked, {defaulted} defaulted to 'To Review'", file=sys.stderr)
    conn.close()


if __name__ == "__main__":
    main()
