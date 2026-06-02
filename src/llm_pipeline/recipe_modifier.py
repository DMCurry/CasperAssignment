"""
Step 2: Recipe Modification

This module applies structured modifications to recipes using search-and-replace operations.
It takes ModificationObject instances and applies their edits to recipe ingredients and instructions.
"""

import copy
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from loguru import logger

from .models import ChangeRecord, ModificationEdit, ModificationObject, Recipe


class RecipeModifier:
    """Applies structured modifications to recipes using search-and-replace operations."""

    def __init__(self, similarity_threshold: float = 0.6):
        """
        Initialize the RecipeModifier.

        Args:
            similarity_threshold: Minimum similarity score for fuzzy matching (0-1)
        """
        self.similarity_threshold = similarity_threshold
        logger.info(
            f"Initialized RecipeModifier with similarity threshold: {similarity_threshold}"
        )

    def find_best_match(
        self, target: str, candidates: List[str]
    ) -> Tuple[Optional[str], Optional[int], float]:
        """
        Find the best matching string in a list of candidates.

        Args:
            target: String to find
            candidates: List of strings to search in

        Returns:
            Tuple of (best_match, index, similarity_score)
        """
        if not candidates:
            return None, None, 0.0

        best_match = None
        best_index = None
        best_score = 0.0

        for i, candidate in enumerate(candidates):
            similarity = SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
            if similarity > best_score:
                best_score = similarity
                best_match = candidate
                best_index = i

        if best_score >= self.similarity_threshold:
            return best_match, best_index, best_score
        return None, None, best_score

    def _make_change_record(
        self,
        edit: ModificationEdit,
        from_text: str,
        to_text: str,
        operation: str,
        line_index: int,
    ) -> ChangeRecord:
        """Build a ChangeRecord from edit metadata and apply result."""
        return ChangeRecord(
            type="ingredient" if edit.target == "ingredients" else "instruction",
            edit_type=edit.edit_type,
            reasoning=edit.reasoning,
            from_text=from_text,
            to_text=to_text,
            operation=operation,
            line_index=line_index,
        )

    def apply_edit(
        self, edit: ModificationEdit, recipe_content: List[str]
    ) -> Tuple[List[str], List[ChangeRecord]]:
        """
        Apply a single edit to a recipe content list.

        Args:
            edit: The edit operation to apply
            recipe_content: List of ingredients or instructions

        Returns:
            Tuple of (modified_content, change_records)
        """
        modified_content = copy.deepcopy(recipe_content)
        change_records: List[ChangeRecord] = []

        logger.debug(
            f"Applying {edit.operation} edit ({edit.insert_mode}): find='{edit.find}'"
        )

        if edit.operation == "replace":
            match, index, score = self.find_best_match(edit.find, modified_content)

            if match and index is not None:
                original_text = modified_content[index]
                if edit.find in original_text:
                    new_text = original_text.replace(edit.find, edit.replace or "")
                elif edit.replace:
                    new_text = edit.replace
                    logger.info(
                        f"Full line replace for '{edit.find}' "
                        f"(substring not found in matched line)"
                    )
                else:
                    logger.warning(
                        f"Could not replace '{edit.find}' in {edit.target} "
                        f"(substring not found, no replacement text)"
                    )
                    return modified_content, change_records

                modified_content[index] = new_text
                change_records.append(
                    self._make_change_record(
                        edit, original_text, new_text, "replace", index
                    )
                )
                logger.info(
                    f"Replaced '{edit.find}' with '{edit.replace}' "
                    f"(similarity: {score:.2f})"
                )
            else:
                logger.warning(
                    f"Could not find '{edit.find}' in {edit.target} "
                    f"(best similarity: {score:.2f})"
                )

        elif edit.operation == "add_after":
            if edit.insert_mode == "append" and edit.add:
                modified_content.append(edit.add)
                line_index = len(modified_content) - 1
                change_records.append(
                    self._make_change_record(edit, "", edit.add, "add", line_index)
                )
                logger.info(f"Appended '{edit.add}' to {edit.target}")
            else:
                match, index, score = self.find_best_match(edit.find, modified_content)

                if match and index is not None and edit.add:
                    modified_content.insert(index + 1, edit.add)
                    line_index = index + 1
                    change_records.append(
                        self._make_change_record(
                            edit, "", edit.add, "add", line_index
                        )
                    )
                    logger.info(
                        f"Added '{edit.add}' after '{edit.find}' "
                        f"(similarity: {score:.2f})"
                    )
                else:
                    logger.warning(f"Could not find target '{edit.find}' for addition")

        elif edit.operation == "remove":
            match, index, score = self.find_best_match(edit.find, modified_content)

            if match and index is not None:
                removed_text = modified_content.pop(index)
                change_records.append(
                    self._make_change_record(
                        edit, removed_text, "", "remove", index
                    )
                )
                logger.info(f"Removed '{edit.find}' (similarity: {score:.2f})")
            else:
                logger.warning(f"Could not find '{edit.find}' to remove")

        return modified_content, change_records

    def apply_modification(
        self, recipe: Recipe, modification: ModificationObject
    ) -> Tuple[Recipe, List[ChangeRecord]]:
        """
        Apply a complete modification to a recipe.

        Ingredient edits are applied before instruction edits so instruction
        sync edits run against an updated ingredient list.

        Args:
            recipe: Original recipe to modify
            modification: Structured modification to apply

        Returns:
            Tuple of (modified_recipe, all_change_records)
        """
        edit_types = list({edit.edit_type for edit in modification.edits})
        logger.info(
            f"Applying {len(modification.edits)} edits "
            f"(types: {edit_types})"
        )

        modified_recipe = Recipe(
            recipe_id=f"{recipe.recipe_id}_modified",
            title=recipe.title,
            ingredients=copy.deepcopy(recipe.ingredients),
            instructions=copy.deepcopy(recipe.instructions),
            description=recipe.description,
            servings=recipe.servings,
            rating=recipe.rating,
        )

        ingredient_edits = [e for e in modification.edits if e.target == "ingredients"]
        instruction_edits = [
            e for e in modification.edits if e.target == "instructions"
        ]
        ordered_edits = ingredient_edits + instruction_edits

        all_change_records: List[ChangeRecord] = []

        for edit in ordered_edits:
            if edit.target == "ingredients":
                modified_recipe.ingredients, change_records = self.apply_edit(
                    edit, modified_recipe.ingredients
                )
            elif edit.target == "instructions":
                modified_recipe.instructions, change_records = self.apply_edit(
                    edit, modified_recipe.instructions
                )
            else:
                logger.warning(f"Unknown edit target: {edit.target}")
                continue

            all_change_records.extend(change_records)

        logger.info(
            f"Applied modification successfully: {len(all_change_records)} changes made"
        )
        return modified_recipe, all_change_records

    def apply_modifications_batch(
        self, recipe: Recipe, modifications: List[ModificationObject]
    ) -> Tuple[Recipe, List[List[ChangeRecord]]]:
        """
        Apply multiple modifications to a recipe sequentially.

        Args:
            recipe: Original recipe to modify
            modifications: List of modifications to apply

        Returns:
            Tuple of (final_modified_recipe, list_of_change_records_per_modification)
        """
        current_recipe = recipe
        all_change_records: List[List[ChangeRecord]] = []

        logger.info(f"Applying {len(modifications)} modifications sequentially")

        for i, modification in enumerate(modifications):
            edit_types = list({edit.edit_type for edit in modification.edits})
            logger.info(
                f"Applying modification {i + 1}/{len(modifications)}: {edit_types}"
            )
            current_recipe, change_records = self.apply_modification(
                current_recipe, modification
            )
            all_change_records.append(change_records)

        logger.info(
            f"Applied all modifications. Final recipe has "
            f"{len(current_recipe.ingredients)} ingredients and "
            f"{len(current_recipe.instructions)} instructions"
        )
        return current_recipe, all_change_records

    def validate_modification_safety(
        self, modification: ModificationObject, recipe: Recipe
    ) -> Tuple[bool, List[str]]:
        """
        Validate that a modification won't break the recipe.

        Args:
            modification: Modification to validate
            recipe: Recipe being modified

        Returns:
            Tuple of (is_safe, list_of_warnings)
        """
        warnings: List[str] = []
        is_safe = True

        for edit in modification.edits:
            if edit.operation == "add_after" and edit.insert_mode == "append":
                if not edit.add:
                    warnings.append("Append add operation missing text to add")
                    is_safe = False
                continue

            target_content = (
                recipe.ingredients
                if edit.target == "ingredients"
                else recipe.instructions
            )
            match, _, score = self.find_best_match(edit.find, target_content)

            if not match:
                warnings.append(f"Cannot find '{edit.find}' in {edit.target}")
                is_safe = False
            elif score < 0.8:
                warnings.append(
                    f"Low similarity match for '{edit.find}' (score: {score:.2f})"
                )

            if edit.operation == "replace" and not edit.replace:
                warnings.append(
                    f"Replace operation missing replacement text for '{edit.find}'"
                )
                is_safe = False
            elif edit.operation == "add_after" and not edit.add:
                warnings.append(
                    f"Add operation missing text to add after '{edit.find}'"
                )
                is_safe = False

        return is_safe, warnings
