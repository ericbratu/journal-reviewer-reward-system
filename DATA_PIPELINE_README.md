# Data Pipeline Setup Guide

This guide explains how to set up the data pipeline for the journal review quality subnet.

## Overview

The data pipeline fetches historical peer reviews from OpenReview and preprocesses them for use by mock miners in the subnet.

## Prerequisites

```bash
pip install -r requirements.txt
```

You'll need:
- `openreview-py` for fetching data
- `openai` for LLM scoring (requires API key)

## Step 1: Fetch OpenReview Data

Fetch papers and reviews from a conference:

```bash
python -m template.data.openreview_fetcher \
    --conference ICLR \
    --year 2023 \
    --output data/raw \
    --limit 100
```

**Arguments:**
- `--conference`: Conference name (ICLR, NeurIPS, ACL)
- `--year`: Conference year (2023, 2024)
- `--output`: Output directory for raw data
- `--limit`: Number of papers to fetch (omit for all papers)

**Output:**
- `data/raw/iclr_2023.json`: Raw paper and review data
- `data/raw/iclr_2023_stats.json`: Dataset statistics

**Note:** Fetching 100 papers takes ~5-10 minutes. Start with `--limit 20` for testing.

## Step 2: Preprocess Data

Process the raw data into miner-ready format:

```bash
python -m template.data.data_preprocessor \
    --input data/raw/iclr_2023.json \
    --output data/processed \
    --num_miners 16
```

**Arguments:**
- `--input`: Path to raw data JSON file
- `--output`: Output directory for processed data
- `--num_miners`: Number of mock miners (default: 16)

**Output:**
- `data/processed/reviews_by_paper.json`: Reviews grouped by paper
- `data/processed/paper_metadata.json`: Paper abstracts and metadata
- `data/processed/all_reviews.json`: Flat list of all reviews
- `data/processed/miner_0_reviews.json` through `miner_15_reviews.json`: Per-miner assignments
- `data/processed/miner_assignments.json`: Assignment summary

## Step 3: Verify Data

Check the processed data:

```python
import json

# Check miner assignments
with open('data/processed/miner_assignments.json') as f:
    assignments = json.load(f)
    print(f"Total miners: {assignments['num_miners']}")
    print(f"Total reviews: {assignments['total_reviews']}")
    print(f"Reviews per miner: {assignments['reviews_per_miner']}")

# Check a sample review
with open('data/processed/miner_0_reviews.json') as f:
    reviews = json.load(f)
    print(f"\nMiner 0 has {len(reviews)} reviews")
    print(f"Sample review: {reviews[0]['review_text'][:200]}...")
```

## Step 4: Set OpenAI API Key

For LLM scoring, set your OpenAI API key:

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-..."

# Linux/Mac
export OPENAI_API_KEY="sk-..."
```

Or create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...
```

## Quick Start (Testing)

For rapid testing with minimal data:

```bash
# Fetch 10 papers
python -m template.data.openreview_fetcher --conference ICLR --year 2023 --limit 10 --output data/raw

# Preprocess for 5 miners
python -m template.data.data_preprocessor --input data/raw/iclr_2023.json --output data/processed --num_miners 5
```

## Data Structure

### Raw Data Format
```json
[
  {
    "paper": {
      "paper_id": "abc123",
      "title": "Paper Title",
      "abstract": "Paper abstract...",
      "decision": "Accept",
      "venue": "ICLR_2023"
    },
    "reviews": [
      {
        "review_id": "rev_1",
        "review_text": "Full review text...",
        "rating": "8: Accept",
        "confidence": "4: Confident",
        "reviewer_id": "Reviewer_ABC"
      }
    ]
  }
]
```

### Processed Review Format
```json
{
  "review_id": "rev_1",
  "paper_id": "abc123",
  "review_text": "Summary: ...\n\nStrengths: ...\n\nWeaknesses: ...",
  "rating": "8: Accept",
  "confidence": "4: Confident",
  "reviewer_id": "Reviewer_ABC",
  "metadata": {
    "paper_title": "Paper Title",
    "venue": "ICLR_2023"
  }
}
```

## Troubleshooting

**Issue: "openreview-py not installed"**
```bash
pip install openreview-py
```

**Issue: "No reviews found for paper X"**
- Some papers may not have public reviews yet
- The preprocessor automatically skips papers without reviews

**Issue: "Rate limit exceeded"**
- OpenReview API has rate limits
- Add delays between requests or reduce `--limit`

**Issue: Empty miner files**
- Check that preprocessing completed successfully
- Verify raw data contains reviews: `cat data/raw/iclr_2023_stats.json`

## Next Steps

After setting up the data pipeline:

1. **Run miners**: See `neurons/miner.py` with `--data_path data/processed --miner_id 0`
2. **Run validator**: See `neurons/validator.py` with `--data_path data/processed --llm_model gpt-4o-mini`
3. **Monitor scoring**: Check logs for LLM rubric scores and rankings

## Cost Estimation

**OpenReview API**: Free, but rate-limited

**OpenAI API** (for scoring):
- Model: `gpt-4o-mini` (~$0.15 per 1M tokens)
- Per review: ~500 tokens input + 200 tokens output = 700 tokens
- 100 reviews: ~70K tokens ≈ $0.01
- Full ICLR dataset (~1500 reviews): ~$0.15

Use caching to avoid re-scoring the same reviews.
