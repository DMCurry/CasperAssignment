"""
Step 3: Enhanced Recipe Generation with Attribution

This module generates enhanced recipes with full citation tracking.
It combines modified recipes with attribution information to create
comprehensive enhanced recipe objects.
"""

from datetime import datetime
from typing import Any, Dict, List

from loguru import logger

from .models import (
    ChangeRecord,
    EnhancedRecipe,
    EnhancementSummary,
    ModificationApplied,
    ModificationObject,
    Recipe,
    Review,
    SourceReview,
)


class EnhancedRecipeGenerator:
    """Generates enhanced recipes with full citation tracking and attribution."""

    def __init__(self, pipeline_version: str = "1.0.0"):
        """
        Initialize the Enhanced Recipe Generator.

        Args:
            pipeline_version: Version identifier for the pipeline
        """
        self.pipeline_version = pipeline_version
        logger.info(f"Initialized EnhancedRecipeGenerator v{pipeline_version}")

    @staticmethod
    def derive_modification_types(change_records: List[ChangeRecord]) -> List[str]:
        """Derive unique modification types from applied change records."""
        return list({change.edit_type for change in change_records})

    @staticmethod
    def derive_summary_reasoning(change_records: List[ChangeRecord]) -> str:
        """Build a summary from unique per-change reasonings."""
        descriptions: List[str] = []
        for change in change_records:
            if change.reasoning and change.reasoning not in descriptions:
                descriptions.append(change.reasoning)
        return "; ".join(descriptions) or "Community-validated recipe improvements"

    def create_source_review(self, review: Review) -> SourceReview:
        """
        Convert a Review object to a SourceReview for attribution.

        Args:
            review: Original review object

        Returns:
            SourceReview with attribution information
        """
        return SourceReview(
            text=review.text,
            reviewer=review.username,
            rating=review.rating,
            review_rank=review.review_rank,
        )

    def create_modification_applied(
        self,
        source_review: Review,
        change_records: List[ChangeRecord],
    ) -> ModificationApplied:
        """
        Create a ModificationApplied record for attribution.

        Args:
            source_review: Review that suggested this modification
            change_records: List of changes that were actually made

        Returns:
            ModificationApplied with full attribution
        """
        return ModificationApplied(
            source_review=self.create_source_review(source_review),
            modification_types=self.derive_modification_types(change_records),
            summary_reasoning=self.derive_summary_reasoning(change_records),
            changes_made=change_records,
        )

    def calculate_enhancement_summary(
        self, modifications_applied: List[ModificationApplied]
    ) -> EnhancementSummary:
        """
        Calculate summary statistics for all applied modifications.

        Args:
            modifications_applied: List of all modifications applied

        Returns:
            EnhancementSummary with aggregate statistics
        """
        total_changes = sum(len(mod.changes_made) for mod in modifications_applied)
        change_types = list(
            {
                change.edit_type
                for mod in modifications_applied
                for change in mod.changes_made
            }
        )

        impact_descriptions: List[str] = []
        for mod in modifications_applied:
            for change in mod.changes_made:
                if change.reasoning and change.reasoning not in impact_descriptions:
                    impact_descriptions.append(change.reasoning)

        expected_impact = "; ".join(impact_descriptions[:3])
        if len(impact_descriptions) > 3:
            expected_impact += (
                f" (and {len(impact_descriptions) - 3} more improvements)"
            )

        return EnhancementSummary(
            total_changes=total_changes,
            change_types=change_types,
            expected_impact=expected_impact
            or "Community-validated recipe improvements",
        )

    def generate_enhanced_recipe(
        self,
        original_recipe: Recipe,
        modified_recipe: Recipe,
        modification: ModificationObject,
        source_review: Review,
        change_records: List[ChangeRecord],
    ) -> EnhancedRecipe:
        """
        Generate a complete enhanced recipe with attribution.

        Args:
            original_recipe: Original unmodified recipe
            modified_recipe: Recipe with modifications applied
            modification: Single modification that was applied
            source_review: Review that suggested the modification
            change_records: Changes made for the modification

        Returns:
            Complete EnhancedRecipe with attribution
        """
        logger.info(f"Generating enhanced recipe for: {original_recipe.title}")

        modification_applied = self.create_modification_applied(
            source_review, change_records
        )
        modifications_applied = [modification_applied]
        enhancement_summary = self.calculate_enhancement_summary(modifications_applied)

        enhanced_recipe = EnhancedRecipe(
            recipe_id=f"{original_recipe.recipe_id}_enhanced",
            original_recipe_id=original_recipe.recipe_id,
            title=f"{original_recipe.title} (Community Enhanced)",
            ingredients=modified_recipe.ingredients,
            instructions=modified_recipe.instructions,
            modifications_applied=modifications_applied,
            enhancement_summary=enhancement_summary,
            description=original_recipe.description,
            servings=original_recipe.servings,
            prep_time=getattr(original_recipe, "prep_time", None),
            cook_time=getattr(original_recipe, "cook_time", None),
            total_time=getattr(original_recipe, "total_time", None),
            created_at=datetime.now().isoformat(),
            pipeline_version=self.pipeline_version,
        )

        logger.info(
            f"Generated enhanced recipe with {enhancement_summary.total_changes} changes "
            f"from {len(modification.edits)} extracted edits"
        )

        return enhanced_recipe

    def generate_comparison_data(
        self, original_recipe: Recipe, enhanced_recipe: EnhancedRecipe
    ) -> Dict[str, Any]:
        """
        Generate side-by-side comparison data for UI display.

        Args:
            original_recipe: Original recipe
            enhanced_recipe: Enhanced recipe

        Returns:
            Dictionary with comparison data
        """
        return {
            "original": {
                "title": original_recipe.title,
                "ingredients": original_recipe.ingredients,
                "instructions": original_recipe.instructions,
                "servings": original_recipe.servings,
            },
            "enhanced": {
                "title": enhanced_recipe.title,
                "ingredients": enhanced_recipe.ingredients,
                "instructions": enhanced_recipe.instructions,
                "servings": enhanced_recipe.servings,
            },
            "changes": {
                "total_modifications": len(enhanced_recipe.modifications_applied),
                "total_changes": enhanced_recipe.enhancement_summary.total_changes,
                "change_types": enhanced_recipe.enhancement_summary.change_types,
                "expected_impact": enhanced_recipe.enhancement_summary.expected_impact,
            },
            "citations": [
                {
                    "reviewer": mod.source_review.reviewer,
                    "rating": mod.source_review.rating,
                    "modification_types": mod.modification_types,
                    "summary_reasoning": mod.summary_reasoning,
                    "changes": [
                        {
                            "type": change.type,
                            "edit_type": change.edit_type,
                            "reasoning": change.reasoning,
                            "from": change.from_text,
                            "to": change.to_text,
                            "operation": change.operation,
                            "line_index": change.line_index,
                        }
                        for change in mod.changes_made
                    ],
                }
                for mod in enhanced_recipe.modifications_applied
            ],
        }

    def save_enhanced_recipe(
        self, enhanced_recipe: EnhancedRecipe, output_path: str
    ) -> str:
        """
        Save enhanced recipe to JSON file.

        Args:
            enhanced_recipe: Enhanced recipe to save
            output_path: Path to save the file

        Returns:
            Path to the saved file
        """
        import json
        import os

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(enhanced_recipe.model_dump(), f, indent=2, ensure_ascii=False)

        logger.info(f"Saved enhanced recipe to: {output_path}")
        return output_path
