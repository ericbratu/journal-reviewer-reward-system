# Journal Review Quality Subnet - Quick Start

This guide gets you running the subnet PoC in under 10 minutes.

## What This Subnet Does

- **Miners**: Replay historical peer reviews from OpenReview (ICLR, NeurIPS, ACL)
- **Validators**: Score review quality using LLM-based rubric evaluation
- **Incentives**: Top-quality reviews earn higher emissions

This is a **proof-of-concept** for incentivizing peer review quality, not real-time reviewing.

## Prerequisites

1. Python 3.8+
2. OpenAI API key (for LLM scoring)
3. ~10 minutes for data setup

## Installation

```bash
# Clone and install
cd journal-reviewer-reward-system
pip install -e .
pip install -r requirements.txt
```

## Step 1: Fetch Sample Data (5 minutes)

```bash
# Fetch 20 papers from ICLR 2023
python -m template.data.openreview_fetcher \
    --conference ICLR \
    --year 2023 \
    --limit 20 \
    --output data/raw
```

Expected output:
```
Fetched 20 papers
Fetching reviews for each paper...
Saved 20 papers with reviews to data/raw/iclr_2023.json
```

## Step 2: Preprocess Data (1 minute)

```bash
# Process for 5 mock miners
python -m template.data.data_preprocessor \
    --input data/raw/iclr_2023.json \
    --output data/processed \
    --num_miners 5
```

Expected output:
```
Processed 20 papers, 60 reviews
Created 5 miner assignment files
Average reviews per miner: 12.0
```

## Step 3: Set API Key

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-key-here"

# Linux/Mac
export OPENAI_API_KEY="sk-your-key-here"
```

## Step 4: Run Local Subnet

### Terminal 1: Start Validator

```bash
python neurons/validator.py \
    --netuid 1 \
    --subtensor.network mock \
    --wallet.name validator \
    --wallet.hotkey default \
    --logging.debug \
    --neuron.sample_size 5 \
    --data_path data/processed \
    --llm_model gpt-4o-mini
```

### Terminal 2-6: Start 5 Miners

```bash
# Miner 0
python neurons/miner.py \
    --netuid 1 \
    --subtensor.network mock \
    --wallet.name miner0 \
    --wallet.hotkey default \
    --logging.debug \
    --data_path data/processed \
    --miner_id 0

# Repeat for miner_id 1, 2, 3, 4 in separate terminals
```

**Tip**: Use a terminal multiplexer like `tmux` or run miners in background.

## What You Should See

**Validator logs:**
```
Querying 5 miners for reviews...
Received 5/5 valid review submissions
Scoring reviews with LLM rubric...
Computed rewards for 5 miners
Reward stats - min: 0.234, max: 1.000, mean: 0.612
```

**Miner logs:**
```
Initialized miner with 12 reviews
Submitted review for paper abc123... (1234 chars)
```

## Understanding the Output

1. **Miners submit reviews**: Each miner sends a historical review from their dataset
2. **Validator groups by paper**: Reviews for the same paper are scored together
3. **LLM scores each review**: Using 6-criteria rubric (comprehension, technical depth, etc.)
4. **Rankings determine rewards**: Top-ranked reviews get exponentially higher rewards
5. **Scores update**: Validator updates miner scores using exponential moving average

## Monitoring

Check validator scores:
```python
import numpy as np

# Load validator state
state = np.load('~/.bittensor/validators/validator/netuid1/state.npz')
print("Miner scores:", state['scores'])
```

## Testing Without OpenAI API

For testing the pipeline without LLM costs:

1. Skip validator, just run miners
2. Or mock the LLM scorer (returns random scores)
3. Or use cached scores from previous runs

## Next Steps

### Experiment with Parameters

- `--neuron.sample_size`: Number of miners to query per epoch
- `--llm_model`: Try `gpt-4o` for better quality (higher cost)
- `--num_miners`: Scale up to 16 miners with more data

### Fetch More Data

```bash
# Full ICLR 2023 dataset (~500 papers)
python -m template.data.openreview_fetcher \
    --conference ICLR \
    --year 2023 \
    --output data/raw
```

### Analyze Results

```bash
# Check which miners are ranking highest
python scripts/analyze_scores.py

# Compare LLM rankings to ground truth
python scripts/evaluate_against_ground_truth.py
```

### Customize Rubric

Edit `template/validator/llm_scorer.py`:
- Modify `RUBRIC_SYSTEM_PROMPT` to change criteria
- Adjust weights in `_validate_and_aggregate()`
- Change reward formula in `score_reviews_grouped()`

## Troubleshooting

**"No reviews available in dataset"**
- Check `data/processed/miner_X_reviews.json` exists
- Verify preprocessing completed successfully

**"Error during scoring: API key not found"**
- Set `OPENAI_API_KEY` environment variable
- Or pass `--openai_api_key` to validator

**"Received 0/5 valid review submissions"**
- Ensure miners are running with correct `--data_path`
- Check miner logs for errors loading dataset

**High API costs**
- Use `--limit 10` when fetching data
- Enable caching (automatic in `data/cache/`)
- Use `gpt-4o-mini` instead of `gpt-4o`

## Architecture Overview

```
OpenReview API
    ↓
[Data Fetcher] → data/raw/iclr_2023.json
    ↓
[Preprocessor] → data/processed/miner_X_reviews.json
    ↓
[Miners] → Submit reviews via ReviewSubmission synapse
    ↓
[Validator] → Score with LLM rubric → Rank → Compute rewards
    ↓
[Bittensor] → Update weights → Distribute emissions
```

## Key Files

- `template/protocol.py`: ReviewSubmission synapse definition
- `template/data/openreview_fetcher.py`: Fetch reviews from OpenReview
- `template/data/data_preprocessor.py`: Normalize and assign reviews to miners
- `template/data/review_dataset.py`: Miner dataset loader
- `neurons/miner.py`: Miner logic (submit reviews)
- `template/validator/llm_scorer.py`: LLM rubric evaluation
- `template/validator/forward.py`: Validator forward pass
- `neurons/validator.py`: Validator entry point

## Support

For issues or questions:
1. Check logs in `~/.bittensor/miners/` and `~/.bittensor/validators/`
2. Review `DATA_PIPELINE_README.md` for detailed setup
3. See architectural plan in project documentation