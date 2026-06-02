# Recipe Enhancement Platform

Automatically enhances recipes by analyzing and applying community-tested modifications from AllRecipes.com. Uses LLM processing to extract meaningful recipe tweaks and apply them with full citation tracking.

## Installation

This project uses [`uv`](https://docs.astral.sh/uv/) for fast, reliable Python package management.

### Prerequisites

- Python 3.13+
- `uv` package manager

## Setup

```bash
# Install dependencies
uv venv
source .venv/bin/activate
uv pip sync pyproject.toml
```

### Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-openai-api-key-here
```

## Usage

### 1. Scrape Recipes (Optional - sample data provided in `data/` at repo root)

```bash
cd src
uv run python scraper_v2.py
```

Scraped recipe JSON is written to `src/data/`. The bundled recipes in `data/` at the repo root are reference samples; the pipeline and tests read from `src/data/`.

Reviews are extracted from **JSON-LD** embedded in the initial HTML (rank-preserving; `review_rank` 0 is the most helpful review). Threaded HTML review cards supplement JSON-LD when present (e.g. browser-rendered pages). A future **Playwright/Selenium** scraper could enrich HTML-only fields if needed.

### 2. Run Recipe Enhancement Pipeline

```bash
cd src

# Test single recipe (chocolate chip cookies)
uv run python test_pipeline.py single

# Process all recipes
uv run python test_pipeline.py all
```

## Output

### Enhanced Recipes

Enhanced recipes are saved in `src/data/enhanced/`:

- `enhanced_[recipe_id]_[recipe-name].json` - Individual enhanced recipes with modifications applied
- `pipeline_summary_report.json` - Summary of all processing results

### Data Structure

Original scraped recipes in `src/data/` contain reviews with `has_modification: true` flags. Enhanced recipes include:

```json
{
  "recipe_id": "10813_enhanced",
  "title": "Best Chocolate Chip Cookies (Community Enhanced)",
  "ingredients": ["1 cup butter", "1 additional egg yolk", ...],
  "modifications_applied": [
    {
      "source_review": {
        "text": "I added an extra egg yolk for chewier texture",
        "rating": 5
      },
      "modification_types": ["addition"],
      "summary_reasoning": "Improves texture and chewiness",
      "changes_made": [
        {
          "type": "ingredient",
          "edit_type": "addition",
          "reasoning": "Reviewer added an extra egg yolk for chewier texture",
          "from_text": "",
          "to_text": "1 additional egg yolk",
          "operation": "add",
          "line_index": 4
        }
      ]
    }
  ],
  "enhancement_summary": {
    "total_changes": 1,
    "change_types": ["addition"],
    "expected_impact": "Chewier texture and improved consistency"
  }
}
```

## How It Works

The LLM Analysis Pipeline processes recipes in 3 steps:

1. **Tweak Extraction**: Tries the review at `review_rank` 0 first, then other modification reviews in rank order, using GPT to extract structured changes
2. **Recipe Modification**: Applies changes to the original recipe using fuzzy string matching
3. **Enhanced Recipe Generation**: Creates enhanced version with full citation tracking back to source review

Review selection uses scraped `review_rank` (0 = most helpful), then star rating as a tiebreaker. Re-scrape from `src/` with `uv run python scraper_v2.py` to refresh `src/data/`.

Each run produces one enhanced recipe per original recipe, with complete attribution showing exactly what changed and why.

## Development

```bash
# Add dependencies
uv add <package_name>

# Run tests
cd src && uv run python test_pipeline.py single
```
