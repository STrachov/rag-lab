# Offer Matcher V2

Updated for the current Upwork strategy: Document AI + evaluated RAG as the target positioning, with data extraction/web scraping retained as a selective cash-flow bridge.

## Main changes
- Separates evaluator instructions from untrusted profile/job data using the Responses API `instructions` field.
- Uses strict JSON Schema output and `store: false`.
- Does not persist the API key in localStorage; removes a legacy saved key.
- Extracts and sends more job-card context: budget/rate, contract type, experience level, duration, proposals, payment verification, client spend/rating, skills, and raw card text when available.
- Deduplicates nested/duplicate job cards.
- Scores technical match, portfolio proof, commercial quality, scope clarity, and strategic value.
- Distinguishes `exact`, `bridge`, `adjacent`, and `weak` matches.
- Distinguishes immediate cash value from value as a new AI proof point.
- Produces an English proposal hook for shortlisted offers.
- Analyzes in batches of 8 and validates that every offer index is returned exactly once.
- Includes metadata in cache hashes and a schema version in the analysis signature.
- Makes the results folder optional; IndexedDB caching and normal JSON downloads still work.

## Run locally
Serve the directory over HTTP so the profile text files can be fetched:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

Keep your existing `styles.css` in the same directory. The updated result view reuses the existing generic result classes.

## Security
This remains a browser-side local utility. The API key is visible to code running on the same page and in browser developer tools. Do not publish this static app on a public site with a real key. For shared or hosted use, move the OpenAI request to a small backend and keep the key in an environment variable.
