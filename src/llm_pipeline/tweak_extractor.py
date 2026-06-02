"""
Step 1: Tweak Extraction & Parsing

This module extracts structured modifications from review text using LLM processing.
It converts natural language descriptions of recipe changes into structured
ModificationObject instances.
"""

import json
import os
from typing import Optional

from loguru import logger
from openai import OpenAI
from pydantic import ValidationError

from .models import ModificationObject, Recipe, Review
from .prompts import SYSTEM_PROMPT, build_few_shot_user_prompt


def rank_modification_reviews(reviews: list[Review]) -> list[Review]:
    """
    Sort modification reviews by scraped review_rank (lower = more helpful).

    Args:
        reviews: All reviews for a recipe

    Returns:
        Modification reviews sorted best-first
    """
    modification_reviews = [review for review in reviews if review.has_modification]

    def sort_key(review: Review) -> tuple[int, int]:
        rank = review.review_rank if review.review_rank is not None else 9999
        return (rank, -(review.rating or 0))

    return sorted(modification_reviews, key=sort_key)


def build_review_candidates(reviews: list[Review]) -> list[Review]:
    """
    Build ordered review candidates for modification extraction.

    Review at rank 0 (most helpful) is tried first, even when regex heuristics
    did not flag it as a modification review. Remaining candidates follow
    review_rank order.
    """
    most_helpful = next(
        (review for review in reviews if review.review_rank == 0),
        next((review for review in reviews if review.is_most_helpful_positive), None),
    )
    ranked_modifications = rank_modification_reviews(reviews)

    candidates: list[Review] = []
    seen_texts: set[str] = set()

    def add_candidate(review: Review) -> None:
        if review.text in seen_texts:
            return
        candidates.append(review)
        seen_texts.add(review.text)

    if most_helpful:
        add_candidate(most_helpful)

    for review in ranked_modifications:
        add_candidate(review)

    return candidates


class TweakExtractor:
    """Extracts structured modifications from review text using LLM processing."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize the TweakExtractor.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use for extraction
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        logger.info(f"Initialized TweakExtractor with model: {model}")

    def extract_modification(
        self,
        review: Review,
        recipe: Recipe,
        max_retries: int = 2,
    ) -> Optional[ModificationObject]:
        """
        Extract a structured modification from a review.

        Args:
            review: Review object containing modification text
            recipe: Original recipe being modified
            max_retries: Number of retry attempts if parsing fails

        Returns:
            ModificationObject if extraction successful, None otherwise
        """
        if not review.has_modification:
            logger.warning("Review has no modification flag set")
            return None

        user_prompt = build_few_shot_user_prompt(
            review.text, recipe.title, recipe.ingredients, recipe.instructions
        )

        logger.debug(
            "Extracting modification from review: {}...".format(review.text[:100])
        )

        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=1000,
                )

                raw_output = response.choices[0].message.content
                logger.debug(f"LLM raw output: {raw_output}")

                if not raw_output:
                    logger.warning(f"Attempt {attempt + 1}: Empty response from LLM")
                    continue

                modification_data = json.loads(raw_output)
                modification = ModificationObject(**modification_data)

                edit_types = list({e.edit_type for e in modification.edits})
                logger.info(
                    f"Successfully extracted {len(modification.edits)} edits "
                    f"(types: {edit_types})"
                )
                return modification

            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt + 1}: Failed to parse JSON: {e}")
                if attempt == max_retries:
                    logger.error(f"Max retries reached. Raw output: {raw_output}")

            except ValidationError as e:
                logger.warning(f"Attempt {attempt + 1}: Validation error: {e}")
                if attempt == max_retries:
                    logger.error(
                        f"Max retries reached. Invalid data: {modification_data}"
                    )

            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Unexpected error: {e}")
                if attempt == max_retries:
                    return None

        return None

    @staticmethod
    def _format_review_selection(review: Review) -> str:
        """Format review metadata for logging."""
        return (
            f"rank={review.review_rank}, "
            f"most_helpful={review.is_most_helpful_positive}, "
            f"rating={review.rating}"
        )

    def extract_single_modification(
        self,
        reviews: list[Review],
        recipe: Recipe,
        review_index: int | None = None,
    ) -> tuple[ModificationObject, Review] | tuple[None, None]:
        """
        Extract modification from a single review.

        By default, tries the review at rank 0 first, then other modification
        reviews in review_rank order. When review_index is set, uses deterministic
        selection for tests.

        Args:
            reviews: List of reviews to choose from
            recipe: Original recipe being modified
            review_index: Optional index into modification reviews for deterministic selection

        Returns:
            Tuple of (ModificationObject, source_Review) if successful, (None, None) otherwise
        """
        modification_reviews = [review for review in reviews if review.has_modification]
        most_helpful = next(
            (review for review in reviews if review.is_most_helpful_positive), None
        )

        if review_index is not None:
            if not modification_reviews:
                logger.warning("No reviews with modifications found")
                return None, None

            if review_index < 0 or review_index >= len(modification_reviews):
                logger.warning(
                    f"review_index {review_index} out of range "
                    f"(0-{len(modification_reviews) - 1})"
                )
                return None, None

            selected_review = modification_reviews[review_index]
            logger.info(
                f"Selected review at index {review_index} "
                f"({self._format_review_selection(selected_review)}): "
                f"{selected_review.text[:100]}..."
            )
            modification = self.extract_modification(selected_review, recipe)
            if modification:
                return modification, selected_review
            logger.warning("Failed to extract modification from selected review")
            return None, None

        ranked_reviews = build_review_candidates(reviews)
        if not ranked_reviews:
            logger.warning("No review candidates found")
            return None, None

        logger.info(
            f"Prepared {len(ranked_reviews)} review candidates "
            "(rank 0 first, then ranked modifications by review_rank)"
        )
        if most_helpful:
            logger.info(
                "Most helpful positive review identified: "
                f"{most_helpful.text[:100]}..."
            )

        for index, candidate in enumerate(ranked_reviews):
            logger.info(
                f"Trying candidate {index + 1}/{len(ranked_reviews)} "
                f"({self._format_review_selection(candidate)}): "
                f"{candidate.text[:100]}..."
            )
            modification = self.extract_modification(candidate, recipe)
            if modification:
                logger.info(
                    f"Selected review ({self._format_review_selection(candidate)})"
                )
                return modification, candidate

            logger.warning(
                f"Extraction failed for review ({self._format_review_selection(candidate)}), "
                "trying next candidate..."
            )

        logger.warning("Failed to extract modification from all ranked reviews")
        return None, None

    def test_extraction(
        self, review_text: str, recipe_data: dict
    ) -> Optional[ModificationObject]:
        """
        Test extraction with raw text and recipe data.

        Args:
            review_text: Raw review text
            recipe_data: Raw recipe dictionary

        Returns:
            ModificationObject if successful
        """
        review = Review(text=review_text, has_modification=True)
        recipe = Recipe(
            recipe_id=recipe_data.get("recipe_id", "test"),
            title=recipe_data.get("title", "Test Recipe"),
            ingredients=recipe_data.get("ingredients", []),
            instructions=recipe_data.get("instructions", []),
        )

        return self.extract_modification(review, recipe)
