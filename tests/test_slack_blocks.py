"""Tests for Block Kit builder functions in watchman.slack.blocks."""

import re
from datetime import datetime

import pytest

from watchman.models.signal_card import SignalCard
from watchman.scoring.models import DimensionScore, RubricScore
from watchman.slack.blocks import (
    build_confirmed_card_blocks,
    build_details_blocks,
    build_review_footer,
    build_signal_card_blocks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_card() -> SignalCard:
    """A minimal SignalCard for use in block builder tests."""
    return SignalCard(
        id=42,
        title="GPT-5 Launches with Multimodal Reasoning",
        source_name="OpenAI Blog",
        date=datetime(2026, 2, 24),
        url="https://openai.com/blog/gpt-5",
        tier=1,
        summary="OpenAI announces GPT-5 with advanced multimodal capabilities.",
        collector_type="rss",
        url_hash=SignalCard.compute_url_hash("https://openai.com/blog/gpt-5"),
        content_fingerprint="abc123",
    )


@pytest.fixture
def sample_score() -> RubricScore:
    """A RubricScore with taxonomy_fit as the top dimension."""
    return RubricScore(
        taxonomy_fit=DimensionScore(score=9.0, rationale="Directly an AI tool release"),
        novel_capability=DimensionScore(score=8.5, rationale="New multimodal approach"),
        adoption_traction=DimensionScore(score=7.0, rationale="Strong pre-launch interest"),
        credibility=DimensionScore(score=9.5, rationale="Official OpenAI announcement"),
        composite_score=8.6,
        top_dimension="taxonomy_fit",
    )


@pytest.fixture
def sample_score_novel(sample_score: RubricScore) -> RubricScore:
    """A RubricScore with novel_capability as the top dimension."""
    return RubricScore(
        taxonomy_fit=sample_score.taxonomy_fit,
        novel_capability=sample_score.novel_capability,
        adoption_traction=sample_score.adoption_traction,
        credibility=sample_score.credibility,
        composite_score=8.2,
        top_dimension="novel_capability",
    )


# ---------------------------------------------------------------------------
# build_signal_card_blocks
# ---------------------------------------------------------------------------


class TestBuildSignalCardBlocks:
    """Tests for build_signal_card_blocks."""

    def test_returns_four_blocks(self, sample_card: SignalCard, sample_score: RubricScore) -> None:
        """Signal card should have exactly 4 blocks: section, context, actions, divider."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        assert len(blocks) == 4

    def test_block_types(self, sample_card: SignalCard, sample_score: RubricScore) -> None:
        """Blocks should be in the correct order: section, context, actions, divider."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        assert blocks[0]["type"] == "section"
        assert blocks[1]["type"] == "context"
        assert blocks[2]["type"] == "actions"
        assert blocks[3]["type"] == "divider"

    def test_score_line_format_taxonomy_fit(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Score line should match 'X.X -- strong taxonomy fit' pattern."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        section_text = blocks[0]["text"]["text"]
        assert "8.6 -- strong taxonomy fit" in section_text

    def test_score_line_format_novel_capability(
        self, sample_card: SignalCard, sample_score_novel: RubricScore
    ) -> None:
        """Score line should reflect the actual top dimension label."""
        blocks = build_signal_card_blocks(sample_card, sample_score_novel)
        section_text = blocks[0]["text"]["text"]
        assert "8.2 -- novel capability" in section_text

    def test_score_line_matches_pattern(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Score line must match the regex pattern 'N.N -- description'."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        section_text = blocks[0]["text"]["text"]
        pattern = re.compile(r"\d+\.\d+ -- .+")
        assert pattern.search(section_text), f"Score line not found in: {section_text}"

    def test_card_url_in_section(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Section block should contain the card URL as a Slack link."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        section_text = blocks[0]["text"]["text"]
        assert sample_card.url in section_text

    def test_four_action_buttons(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Actions block should contain exactly 4 buttons."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        actions_block = blocks[2]
        assert len(actions_block["elements"]) == 4

    def test_action_button_ids(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Each button should have the correct action_id."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        action_ids = [btn["action_id"] for btn in blocks[2]["elements"]]
        assert "approve_card" in action_ids
        assert "reject_card" in action_ids
        assert "snooze_card" in action_ids
        assert "details_card" in action_ids

    def test_approve_button_primary_style(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Approve button should have 'primary' style."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        approve_btn = next(
            b for b in blocks[2]["elements"] if b["action_id"] == "approve_card"
        )
        assert approve_btn["style"] == "primary"

    def test_reject_button_danger_style(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Reject button should have 'danger' style."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        reject_btn = next(
            b for b in blocks[2]["elements"] if b["action_id"] == "reject_card"
        )
        assert reject_btn["style"] == "danger"

    def test_button_values_are_card_id(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Each button's value should be the card ID as a string."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        for btn in blocks[2]["elements"]:
            assert btn["value"] == str(sample_card.id)

    def test_source_name_in_context(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Context block should include the source name."""
        blocks = build_signal_card_blocks(sample_card, sample_score)
        context_text = blocks[1]["elements"][0]["text"]
        assert "OpenAI Blog" in context_text


# ---------------------------------------------------------------------------
# build_confirmed_card_blocks
# ---------------------------------------------------------------------------


class TestBuildConfirmedCardBlocks:
    """Tests for build_confirmed_card_blocks."""

    def test_no_action_blocks_after_approve(self, sample_card: SignalCard) -> None:
        """Confirmed card should not contain any 'actions' blocks."""
        blocks = build_confirmed_card_blocks(sample_card, "approved")
        block_types = [b["type"] for b in blocks]
        assert "actions" not in block_types

    def test_no_action_blocks_after_reject(self, sample_card: SignalCard) -> None:
        """Confirmed card should not contain any 'actions' blocks after rejection."""
        blocks = build_confirmed_card_blocks(sample_card, "rejected")
        block_types = [b["type"] for b in blocks]
        assert "actions" not in block_types

    def test_no_action_blocks_after_snooze(self, sample_card: SignalCard) -> None:
        """Confirmed card should not contain any 'actions' blocks after snooze."""
        blocks = build_confirmed_card_blocks(sample_card, "snoozed")
        block_types = [b["type"] for b in blocks]
        assert "actions" not in block_types

    def test_approved_shows_checkmark(self, sample_card: SignalCard) -> None:
        """Approved card should show a checkmark indicator."""
        blocks = build_confirmed_card_blocks(sample_card, "approved")
        text = blocks[0]["text"]["text"]
        assert "Approved" in text

    def test_rejected_shows_x(self, sample_card: SignalCard) -> None:
        """Rejected card should show an X indicator."""
        blocks = build_confirmed_card_blocks(sample_card, "rejected")
        text = blocks[0]["text"]["text"]
        assert "Rejected" in text

    def test_snoozed_shows_clock(self, sample_card: SignalCard) -> None:
        """Snoozed card should mention snoozed duration."""
        blocks = build_confirmed_card_blocks(sample_card, "snoozed")
        text = blocks[0]["text"]["text"]
        assert "Snoozed" in text or "30 days" in text

    def test_card_url_preserved(self, sample_card: SignalCard) -> None:
        """Confirmed card should still link to the original URL."""
        blocks = build_confirmed_card_blocks(sample_card, "approved")
        text = blocks[0]["text"]["text"]
        assert sample_card.url in text


# ---------------------------------------------------------------------------
# build_review_footer
# ---------------------------------------------------------------------------


class TestBuildReviewFooter:
    """Tests for build_review_footer."""

    def test_footer_format(self) -> None:
        """Footer should contain 'Showing X of Y signals today'."""
        blocks = build_review_footer(showing=5, total=12)
        context_text = blocks[0]["elements"][0]["text"]
        assert "Showing 5 of 12 signals today" in context_text

    def test_footer_is_context_block(self) -> None:
        """Footer should use a 'context' block type."""
        blocks = build_review_footer(showing=3, total=7)
        assert blocks[0]["type"] == "context"

    def test_footer_edge_case_zero(self) -> None:
        """Footer should handle zero counts gracefully."""
        blocks = build_review_footer(showing=0, total=0)
        context_text = blocks[0]["elements"][0]["text"]
        assert "Showing 0 of 0 signals today" in context_text

    def test_footer_showing_equals_total(self) -> None:
        """Footer should format correctly when showing equals total."""
        blocks = build_review_footer(showing=5, total=5)
        context_text = blocks[0]["elements"][0]["text"]
        assert "Showing 5 of 5 signals today" in context_text


# ---------------------------------------------------------------------------
# build_details_blocks
# ---------------------------------------------------------------------------


class TestBuildDetailsBlocks:
    """Tests for build_details_blocks."""

    def test_includes_all_four_dimensions(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Details should include all 4 rubric dimension names."""
        blocks = build_details_blocks(sample_card, sample_score)
        full_text = " ".join(
            b.get("text", {}).get("text", "") for b in blocks if b.get("text")
        )
        assert "Taxonomy Fit" in full_text
        assert "Novel Capability" in full_text
        assert "Adoption Traction" in full_text
        assert "Credibility" in full_text

    def test_includes_dimension_scores(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Details should include numeric scores for each dimension."""
        blocks = build_details_blocks(sample_card, sample_score)
        full_text = " ".join(
            b.get("text", {}).get("text", "") for b in blocks if b.get("text")
        )
        assert "9.0" in full_text
        assert "8.5" in full_text
        assert "7.0" in full_text
        assert "9.5" in full_text

    def test_includes_rationales(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Details should include dimension rationale text."""
        blocks = build_details_blocks(sample_card, sample_score)
        full_text = " ".join(
            b.get("text", {}).get("text", "") for b in blocks if b.get("text")
        )
        assert "Directly an AI tool release" in full_text

    def test_includes_composite_score(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Details should display the composite score somewhere in the blocks."""
        blocks = build_details_blocks(sample_card, sample_score)
        # Extract text from section blocks and context element blocks
        all_texts = []
        for block in blocks:
            if block.get("text"):
                all_texts.append(block["text"].get("text", ""))
            for elem in block.get("elements", []):
                all_texts.append(elem.get("text", ""))
        full_text = " ".join(all_texts)
        assert "8.6" in full_text

    def test_block_count_reasonable(
        self, sample_card: SignalCard, sample_score: RubricScore
    ) -> None:
        """Details should return at least 2 blocks (header + content)."""
        blocks = build_details_blocks(sample_card, sample_score)
        assert len(blocks) >= 2
