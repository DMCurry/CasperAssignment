# Assignment Document

## Problem analysis and solution approach

### Problem

- After running `test_pipeline.py all` I could tell that at least the application was able to run.  
- After getting an idea of how the core code worked with the pipeline and models, I had cursor look into some issues with the default test_pipeline setup and identify some core logic and architectural flaws.
  1. Test cases did not cover enough and assertions were very basic  
  2. The models that validate output were unable to support reviews with multiple modifications  
  3. Safety code for failed extraction mapping to output structure was basically dead code

## Technical decisions and rationale

- I updated the structure of the models to support multiple modification types  
  - Rationale: There are reviews with multiple changes
- I updated the integration tests
  - Rationale: The tests were making much too simple of assertions and needed to confirm proper enrichment given different reviews
- I fixed some safety check code that was not called  
  - Rationale: This was a useful function that handled failed review extraction
- I changed the pipeline to first consider the ingredient changes and then update the instructions to fix some weirdness in the modified instructions where steps were out of order or oddly placed. Having the models and prompts be more explicit and organized with new fields was also part of this update
  - Rationale: The instructions were unclear and it would end up as a user experience that is worse than just getting the original recipe
- I made the diff output more robust by adding another object on the enriched output (ChangeRecord)  
  - Rationale: This is a clean way to add more explicit diff information to each enriched recipe
- I updated the scraper to use JSON Linked Data for the reviews to make sure it is considering the most helpful positive review to incorporate into the recipe (These results are automatically sorted by most helpful positive)  
  - Rationale: This makes sense because users would naturally want the most popular modifications

## Future improvements

- Using Playwright or Selenium headless web driver technology would offere more power and flexibility potentially. As I understood there is no API for AllRecipes  
- A more full on test framework (pytest for example) should be incorporated with unit tests and more integration tests potentially  
- This can be turned into a backend API that communicates with a simple front-end that lets users search a recipe:  
  1. Users search in search bar  
  2. Send request to backend (Maybe FastAPI to keep it simple and scalable)  
  3. Backend uses Playwright or Selenium rather than scraper to locate Allrecipes search and query using the user query  
  4. Return results and feed into LLM pipeline to enrich recipes with reviews  
  5. Return enriched content to front end and highlight diff in UI to show modifications with reasoning.

