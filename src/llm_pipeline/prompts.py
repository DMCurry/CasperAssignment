"""
LLM prompts and examples for recipe modification extraction.

This module contains carefully crafted prompts for extracting structured
modifications from user review text.
"""

SYSTEM_PROMPT = """You are an expert recipe analyst. Your job is to extract structured recipe modifications from user reviews.

When a user shares their experience modifying a recipe, you need to:
1. Identify exactly what changes they made
2. Understand why they made each change
3. Convert their modifications into structured edit operations

You must output valid JSON that matches the ModificationObject schema.

Edit categories (edit_type — one per edit):
- "ingredient_substitution": Replacing one ingredient with another
- "quantity_adjustment": Changing amounts of existing ingredients
- "technique_change": Altering cooking method, temperature, time
- "addition": Adding new ingredients or steps
- "removal": Removing ingredients or steps

Edit operations:
- "replace": Find existing text and replace it
- "add_after": Add new text after finding target text, or append to list end
- "remove": Remove text that matches the find pattern

Insert modes (insert_mode):
- "after_find": Insert after the line matched by find (default for replace/remove)
- "append": Append to the end of the ingredients or instructions list (use for final steps like drizzle/garnish, or new ingredients at end of list)

Extraction rules:
- Extract EVERY distinct change as a separate edit; each edit MUST include edit_type and reasoning
- When the reviewer uses relative language (e.g. "halved the sugar"), compute absolute amounts from the recipe
- Use the exact ingredient or instruction line text from the recipe for the find field
- Instruction sync: when an ingredient is substituted, removed, or renamed, include matching instructions replace edits for any step that mentions the old ingredient text
- List ingredient edits before their related instruction sync edits
- Focus on concrete changes the user actually made, not general suggestions or future intentions"""

EXTRACTION_PROMPT = """Original Recipe:
Title: {title}
Ingredients: {ingredients}
Instructions: {instructions}

User Review: "{review_text}"

Extract the recipe modifications from this review. The user has made changes to improve the recipe.

Output a JSON object with this structure:
{{
    "edits": [
        {{
            "edit_type": "ingredient_substitution|quantity_adjustment|technique_change|addition|removal",
            "reasoning": "Why this specific edit improves the recipe",
            "target": "ingredients|instructions",
            "operation": "replace|add_after|remove",
            "find": "exact text to find",
            "replace": "replacement text (for replace operations)",
            "add": "text to add (for add_after operations)",
            "insert_mode": "after_find|append"
        }}
    ]
}}"""

FEW_SHOT_EXAMPLES = [
    {
        "review": "I used a half cup of sugar and one-and-a-half cups of brown sugar instead of the recipe amounts. Made the cookies much more chewy and flavorful!",
        "ingredients": [
            "1 cup butter, softened",
            "1 cup white sugar",
            "1 cup packed brown sugar",
            "2 eggs",
        ],
        "instructions": [],
        "expected_output": {
            "edits": [
                {
                    "edit_type": "quantity_adjustment",
                    "reasoning": "Reviewer reduced white sugar to half cup for less sweetness",
                    "target": "ingredients",
                    "operation": "replace",
                    "find": "1 cup white sugar",
                    "replace": "0.5 cup white sugar",
                    "insert_mode": "after_find",
                },
                {
                    "edit_type": "quantity_adjustment",
                    "reasoning": "Reviewer increased brown sugar for chewier, more flavorful cookies",
                    "target": "ingredients",
                    "operation": "replace",
                    "find": "1 cup packed brown sugar",
                    "replace": "1.5 cups packed brown sugar",
                    "insert_mode": "after_find",
                },
            ],
        },
    },
    {
        "review": "I substituted 2% milk instead of half-and-half. Still creamy and delicious!",
        "ingredients": [
            "3 cups chicken broth",
            "1.5 cups half-and-half (or whole milk)",
        ],
        "instructions": [
            "Puree until smooth, then stir in half-and-half.",
            "Ladle into bowls and serve.",
        ],
        "expected_output": {
            "edits": [
                {
                    "edit_type": "ingredient_substitution",
                    "reasoning": "Reviewer substituted 2% milk for half-and-half",
                    "target": "ingredients",
                    "operation": "replace",
                    "find": "1.5 cups half-and-half (or whole milk)",
                    "replace": "2% milk",
                    "insert_mode": "after_find",
                },
                {
                    "edit_type": "ingredient_substitution",
                    "reasoning": "Update puree step to reference milk instead of half-and-half",
                    "target": "instructions",
                    "operation": "replace",
                    "find": "Puree until smooth, then stir in half-and-half.",
                    "replace": "Puree until smooth, then stir in 2% milk.",
                    "insert_mode": "after_find",
                },
            ],
        },
    },
    {
        "review": "I added an egg and halved the sugar.",
        "ingredients": [
            "1 cup butter, softened",
            "1 cup white sugar",
            "1 cup packed brown sugar",
            "2 eggs",
        ],
        "instructions": [],
        "expected_output": {
            "edits": [
                {
                    "edit_type": "addition",
                    "reasoning": "Reviewer added an extra egg for richness",
                    "target": "ingredients",
                    "operation": "replace",
                    "find": "2 eggs",
                    "replace": "3 eggs",
                    "insert_mode": "after_find",
                },
                {
                    "edit_type": "quantity_adjustment",
                    "reasoning": "Reviewer halved the white sugar amount",
                    "target": "ingredients",
                    "operation": "replace",
                    "find": "1 cup white sugar",
                    "replace": "0.5 cup white sugar",
                    "insert_mode": "after_find",
                },
            ],
        },
    },
    {
        "review": "I drizzled heavy cream at the end before serving. Turned out amazing!",
        "ingredients": ["3 cups broth", "1 cup cream"],
        "instructions": [
            "Gather the ingredients.",
            "Simmer soup until tender.",
            "Ladle into bowls and serve.",
        ],
        "expected_output": {
            "edits": [
                {
                    "edit_type": "addition",
                    "reasoning": "Reviewer added a final drizzle of heavy cream before serving",
                    "target": "instructions",
                    "operation": "add_after",
                    "find": "",
                    "add": "Drizzle heavy cream over each bowl before serving.",
                    "insert_mode": "append",
                },
            ],
        },
    },
]


def build_few_shot_prompt(
    review_text: str, title: str, ingredients: list, instructions: list
) -> str:
    """Build a few-shot user prompt with examples for extraction."""
    return build_few_shot_user_prompt(
        review_text, title, ingredients, instructions
    )


def build_few_shot_user_prompt(
    review_text: str, title: str, ingredients: list, instructions: list
) -> str:
    """Build the user message content with few-shot examples."""
    examples_text = "\n\n".join(
        [
            f"Example {i + 1}:\n"
            f'Review: "{example["review"]}"\n'
            f"Output: {example['expected_output']}"
            for i, example in enumerate(FEW_SHOT_EXAMPLES)
        ]
    )

    extraction_request = EXTRACTION_PROMPT.format(
        title=title,
        ingredients=ingredients,
        instructions=instructions,
        review_text=review_text,
    )

    return f"""Here are some examples of how to extract modifications:

{examples_text}

Now extract from this review:

{extraction_request}"""


def build_simple_prompt(
    review_text: str, title: str, ingredients: list, instructions: list
) -> str:
    """Build a simple user prompt without examples."""
    return EXTRACTION_PROMPT.format(
        title=title,
        ingredients=ingredients,
        instructions=instructions,
        review_text=review_text,
    )
