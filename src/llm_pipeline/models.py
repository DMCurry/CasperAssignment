"""
Pydantic data models for the LLM Analysis Pipeline.

These models define the structure for recipe modifications, enhanced recipes,
and all intermediate data formats used throughout the pipeline.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ModificationType = Literal[
    "ingredient_substitution",
    "quantity_adjustment",
    "technique_change",
    "addition",
    "removal",
]

InsertMode = Literal["after_find", "append"]


class ModificationEdit(BaseModel):
    """Individual atomic edit operation for a recipe modification."""

    edit_type: ModificationType = Field(description="Category of this specific edit")
    reasoning: str = Field(description="Why this specific edit improves the recipe")
    target: Literal["ingredients", "instructions"] = Field(
        description="Whether this edit applies to ingredients or instructions"
    )
    operation: Literal["replace", "add_after", "remove"] = Field(
        default="replace",
        description="Type of operation: replace text, add after target, or remove",
    )
    find: str = Field(description="Text to find in the recipe")
    replace: Optional[str] = Field(
        default=None, description="Replacement text (required for replace operations)"
    )
    add: Optional[str] = Field(
        default=None, description="Text to add (required for add_after operations)"
    )
    insert_mode: InsertMode = Field(
        default="after_find",
        description="Where to insert new content: after a matched line or at list end",
    )


class ModificationObject(BaseModel):
    """Structured modification parsed from a review."""

    edits: List[ModificationEdit] = Field(description="List of atomic edits to apply")


class SourceReview(BaseModel):
    """Reference to the original review that suggested the modification."""

    text: str = Field(description="Full text of the original review")
    reviewer: Optional[str] = Field(description="Username of the reviewer")
    rating: Optional[int] = Field(description="Star rating given by reviewer")
    review_rank: Optional[int] = Field(
        default=None, description="0-based rank from scraped review order (0 = most helpful)"
    )


class ChangeRecord(BaseModel):
    """Record of a specific change made to the recipe."""

    type: Literal["ingredient", "instruction"] = Field(
        description="Type of element that was changed"
    )
    edit_type: ModificationType = Field(description="Category of this specific change")
    reasoning: str = Field(description="Why this specific change was applied")
    from_text: str = Field(description="Original text before modification")
    to_text: str = Field(description="New text after modification")
    operation: Literal["replace", "add", "remove"] = Field(
        description="Type of operation performed"
    )
    line_index: int = Field(
        description="0-based index in the target list after the edit was applied"
    )


class ModificationApplied(BaseModel):
    """Full record of a modification that was applied to a recipe."""

    source_review: SourceReview = Field(
        description="Review that suggested this modification"
    )
    modification_types: List[str] = Field(
        description="Categories of modification, derived from changes_made"
    )
    summary_reasoning: str = Field(
        description="Combined summary of why changes were applied"
    )
    changes_made: List[ChangeRecord] = Field(
        description="Detailed list of changes made"
    )


class EnhancementSummary(BaseModel):
    """Summary of all modifications applied to a recipe."""

    total_changes: int = Field(description="Total number of changes made")
    change_types: List[str] = Field(description="Types of modifications applied")
    expected_impact: str = Field(
        description="Expected improvement from these modifications"
    )


class EnhancedRecipe(BaseModel):
    """Recipe with community modifications applied and full attribution."""

    recipe_id: str = Field(description="Enhanced recipe ID")
    original_recipe_id: str = Field(description="ID of the original recipe")
    title: str = Field(description="Enhanced recipe title")

    # Enhanced recipe content
    ingredients: List[str] = Field(description="Modified ingredients list")
    instructions: List[str] = Field(description="Modified instructions list")

    # Attribution and tracking
    modifications_applied: List[ModificationApplied] = Field(
        description="Full record of all modifications applied"
    )
    enhancement_summary: EnhancementSummary = Field(
        description="Summary of all enhancements"
    )

    # Optional metadata
    description: Optional[str] = Field(description="Enhanced recipe description")
    servings: Optional[str] = Field(description="Number of servings")
    prep_time: Optional[str] = Field(description="Preparation time")
    cook_time: Optional[str] = Field(description="Cooking time")
    total_time: Optional[str] = Field(description="Total time")

    # Generation metadata
    created_at: str = Field(description="When this enhanced recipe was created")
    pipeline_version: str = Field(
        default="1.0.0", description="Version of the pipeline that created this"
    )


class Recipe(BaseModel):
    """Base recipe model for input data."""

    recipe_id: str
    title: str
    ingredients: List[str]
    instructions: List[str]
    description: Optional[str] = None
    servings: Optional[str] = None
    rating: Optional[Dict[str, Any]] = None


class Review(BaseModel):
    """Review model for input data."""

    text: str
    rating: Optional[int] = None
    username: Optional[str] = None
    has_modification: bool = False
    review_rank: Optional[int] = Field(
        default=None,
        description="0-based rank from AllRecipes JSON-LD order (0 = most helpful)",
    )
    is_most_helpful_positive: bool = False
    is_featured: bool = False  # legacy alias; prefer is_most_helpful_positive
