#!/usr/bin/env python3
"""
LLM Analysis Pipeline Test Script

This script tests the complete 3-step pipeline with support for both single recipe
testing and full recipe directory validation.

Usage:
    python test_pipeline.py single    # Test single chocolate chip cookie recipe
    python test_pipeline.py all       # Test all recipes in data directory
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from llm_pipeline.models import EnhancedRecipe
from llm_pipeline.pipeline import LLMAnalysisPipeline

# Load environment variables from .env file
load_dotenv()

# Index 1 in modification reviews for the 4-tweak compound cookie review
COMPOUND_REVIEW_INDEX = 1


def assert_enhanced_recipe(enhanced_recipe: EnhancedRecipe) -> None:
    """Validate structural expectations on an enhanced recipe output."""
    assert len(enhanced_recipe.modifications_applied) >= 1, (
        "Expected at least one modification to be applied"
    )

    mod = enhanced_recipe.modifications_applied[0]
    assert len(mod.changes_made) > 0, "Expected at least one change to be applied"
    assert len(mod.modification_types) >= 1, (
        "Expected at least one modification type"
    )

    expected_total = sum(
        len(m.changes_made) for m in enhanced_recipe.modifications_applied
    )
    assert enhanced_recipe.enhancement_summary.total_changes == expected_total, (
        f"Summary total_changes ({enhanced_recipe.enhancement_summary.total_changes}) "
        f"does not match sum of changes_made ({expected_total})"
    )


def log_compound_review_warnings(enhanced_recipe: EnhancedRecipe) -> None:
    """Log soft warnings when a compound review may have been under-extracted."""
    mod = enhanced_recipe.modifications_applied[0]
    edit_count = len(mod.changes_made)
    type_count = len(mod.modification_types)

    if edit_count < 2:
        logger.warning(
            f"Compound review check: only {edit_count} edit(s) applied "
            "(expected >= 2 for multi-change reviews)"
        )
    if type_count < 2:
        logger.warning(
            f"Compound review check: only {type_count} modification type(s) "
            "(expected >= 2 for compound reviews)"
        )


def test_single_recipe():
    """Test the pipeline with the chocolate chip cookie compound review."""

    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        logger.info("Please set your OpenAI API key in .env file")
        return False

    try:
        pipeline = LLMAnalysisPipeline()
        logger.info("Pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        return False

    recipe_file = "../data/recipe_10813_best-chocolate-chip-cookies.json"
    if not Path(recipe_file).exists():
        logger.error(f"Recipe file not found: {recipe_file}")
        return False

    logger.info(f"Testing with recipe file: {recipe_file}")
    logger.info(
        f"Using review_index={COMPOUND_REVIEW_INDEX} "
        "(4-tweak compound cookie review)"
    )

    try:
        enhanced_recipe = pipeline.process_single_recipe(
            recipe_file=recipe_file,
            save_output=True,
            review_index=COMPOUND_REVIEW_INDEX,
        )

        if not enhanced_recipe:
            logger.error("✗ Single recipe test failed - no enhanced recipe generated")
            return False

        assert_enhanced_recipe(enhanced_recipe)
        log_compound_review_warnings(enhanced_recipe)

        mod = enhanced_recipe.modifications_applied[0]
        logger.success("✓ Single recipe test successful!")
        logger.info(f"Enhanced recipe: {enhanced_recipe.title}")
        logger.info(f"Modifications applied: {len(enhanced_recipe.modifications_applied)}")
        logger.info(f"Modification types: {mod.modification_types}")
        logger.info(f"Changes made: {len(mod.changes_made)}")
        logger.info(f"Total changes: {enhanced_recipe.enhancement_summary.total_changes}")
        logger.info(f"Expected impact: {enhanced_recipe.enhancement_summary.expected_impact}")
        return True

    except AssertionError as e:
        logger.error(f"✗ Single recipe test failed assertion: {e}")
        return False
    except Exception as e:
        logger.error(f"Single recipe test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def recipe_has_modification_reviews(
    pipeline: LLMAnalysisPipeline, recipe_file: str
) -> bool:
    """Return True if the recipe file has at least one review flagged with modifications."""
    recipe_data = pipeline.load_recipe_data(recipe_file)
    reviews = pipeline.parse_reviews_data(recipe_data)
    return any(r.has_modification for r in reviews)


def test_all_recipes():
    """Test the pipeline with all scraped recipes."""

    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        logger.info("Please set your OpenAI API key in .env file")
        return False

    try:
        pipeline = LLMAnalysisPipeline()
        logger.info("Pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        return False

    data_dir = Path("../data")
    recipe_files = sorted(data_dir.glob("recipe_*.json"))

    try:
        enhanced_recipes = []
        skipped_recipes = []
        failed_recipes = []

        for recipe_file in recipe_files:
            logger.info(f"\nProcessing: {recipe_file.name}")

            if not recipe_has_modification_reviews(pipeline, str(recipe_file)):
                skipped_recipes.append(
                    (recipe_file.name, "no modification reviews in scraped data")
                )
                logger.info(
                    f"○ Skipped: {recipe_file.name} "
                    "(no modification reviews — expected for some scraped recipes)"
                )
                continue

            enhanced_recipe = pipeline.process_single_recipe(
                str(recipe_file), save_output=True
            )

            if enhanced_recipe:
                try:
                    assert_enhanced_recipe(enhanced_recipe)
                    enhanced_recipes.append(enhanced_recipe)
                    logger.info(f"✓ Passed: {enhanced_recipe.title}")
                except AssertionError as e:
                    failed_recipes.append((recipe_file.name, f"assertion: {e}"))
                    logger.warning(f"✗ Failed assertion for {recipe_file.name}: {e}")
            else:
                failed_recipes.append(
                    (recipe_file.name, "pipeline returned no enhanced recipe")
                )
                logger.warning(f"✗ Failed: {recipe_file.name}")

        report_path = pipeline.save_summary_report(enhanced_recipes)

        logger.info(f"\n{'=' * 60}")
        logger.info(
            f"Successful: {len(enhanced_recipes)}/{len(recipe_files)} "
            f"({len(skipped_recipes)} skipped, {len(failed_recipes)} failed)"
        )
        logger.info(f"Summary report saved to: {report_path}")

        if skipped_recipes:
            logger.info("Skipped recipes (expected — no modification review data):")
            for name, reason in skipped_recipes:
                logger.info(f"  - {name}: {reason}")

        if failed_recipes:
            logger.warning("Failed recipes:")
            for name, reason in failed_recipes:
                logger.warning(f"  - {name}: {reason}")

        if enhanced_recipes and not failed_recipes:
            logger.success("✓ All recipes test complete!")
            return True

        if not enhanced_recipes:
            logger.error("✗ All recipes test failed - zero recipes succeeded")
            return False

        logger.error("✗ All recipes test failed - one or more processable recipes failed")
        return False

    except Exception as e:
        logger.error(f"All recipes test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main test function with mode selection."""

    if len(sys.argv) < 2:
        logger.error("Usage: python test_pipeline.py [single|all]")
        logger.info("  single - Test single chocolate chip cookie recipe (compound review)")
        logger.info("  all    - Test all recipes in data directory")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "single":
        logger.info("Starting LLM Analysis Pipeline - Single Recipe Test")
        logger.info("=" * 60)
        success = test_single_recipe()

        logger.info("=" * 60)
        if success:
            logger.success("Single recipe test passed! ✓")
            logger.info("Check the 'data/enhanced/' directory for the enhanced recipe.")
        else:
            logger.error("Single recipe test failed! ✗")
            sys.exit(1)

    elif mode == "all":
        logger.info("Starting LLM Analysis Pipeline - All Recipes Validation")
        logger.info("=" * 60)
        success = test_all_recipes()

        logger.info("=" * 60)
        if success:
            logger.success("All recipes validation passed! ✓")
            logger.info("Check the 'data/enhanced/' directory for all enhanced recipes.")
            logger.info("Check 'data/enhanced/pipeline_summary_report.json' for detailed results.")
        else:
            logger.error("All recipes validation failed! ✗")
            sys.exit(1)

    else:
        logger.error(f"Unknown mode: {mode}")
        logger.error("Usage: python test_pipeline.py [single|all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
