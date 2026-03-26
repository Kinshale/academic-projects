# Scraped Data Testing Pipeline

This directory contains notebooks for testing trained models on real-world data scraped from the Bluesky Firehose API.

## Data Source

**Period:** December 31, 2025 - January 16, 2026 (with some gaps)  
**Location:** `data/scraped/cleaned/`  
**Files:** blocks.parquet, follows.parquet, likes.parquet, posts.parquet, profiles.parquet

**Note:** Due to gaps in the crawled data, activity counts are multiplied by 1.2 to compensate.

## Pipeline Overview

### 1. Filter Users (`1-filter-users-scraped.ipynb`)

**Purpose:** Identify users of interest and filter relevant events

**Process:**
- Identifies users who blocked someone in their first week (days 0-6)
- Filters all events (blocks, posts, follows, likes) to include:
  - Events involving these users
  - Events occurring within 7 days of their join date

**Output:** 
- `data/ale_simplicistic_model/scraped/filtered/first_week_blockers.parquet`
- `data/ale_simplicistic_model/scraped/filtered/{blocks,posts,follows,likes}.parquet`

### 2. Process Data (`2-process-scraped.ipynb`)

**Purpose:** Create 7-day activity vectors for each user

**Process:**
- Groups events by day relative to each user's join date
- Creates activity vectors for days 0-6:
  - Posts (single-user events)
  - Blocks initiated/received (two-user events)
  - Follows made/received (two-user events)
  - Likes made/received (two-user events)
- **Multiplies counts by 1.2** to compensate for data gaps

**Output:** 
- `data/ale_simplicistic_model/scraped/processed/user_activity.parquet`

### 3. Feature Engineering & Testing (`3-feature-engineering-and-test.ipynb`)

**Purpose:** Apply feature engineering and test pre-trained models

**Process:**
1. Loads processed user activity data
2. Applies feature engineering using `feature_engineering_utils.py`
3. Loads pre-trained models from `data/ale_simplicistic_model/relative/model_ready/`
4. Generates ground truth labels by checking blocks in weeks 2, 3, and 4
5. Makes predictions and evaluates performance
6. Compares results with training performance
7. Visualizes results

**Output:**
- `data/ale_simplicistic_model/scraped/model_results.parquet` (and .csv)
- `data/ale_simplicistic_model/scraped/model_performance.png`

## Models Tested

Three model types for three prediction horizons:

| Model Type | Week 2 | Week 3 | Week 4 |
|------------|--------|--------|--------|
| Logistic Regression | ✓ | ✓ | ✓ |
| Random Forest | ✓ | ✓ | ✓ |
| Gradient Boosting | ✓ | ✓ | ✓ |

**Prediction Targets:**
- Week 2: Blocks in days 7-13
- Week 3: Blocks in days 14-20
- Week 4: Blocks in days 21-27

## Evaluation Metrics

- **Accuracy:** Overall correctness
- **Precision:** True positives / (True positives + False positives)
- **Recall:** True positives / (True positives + False negatives)
- **F1-Score:** Harmonic mean of precision and recall
- **ROC-AUC:** Area under the ROC curve
- **Confusion Matrix:** TN, FP, FN, TP counts

## Running the Pipeline

Execute notebooks in order:

```bash
# 1. Filter users and events
jupyter notebook 1-filter-users-scraped.ipynb

# 2. Process into activity vectors
jupyter notebook 2-process-scraped.ipynb

# 3. Feature engineering and model testing
jupyter notebook 3-feature-engineering-and-test.ipynb
```

## Key Differences from Training Pipeline

1. **No sampling:** Uses all users who blocked in first week (not limited to 100k sample)
2. **Data gaps compensation:** Activity multiplied by 1.2
3. **Relative sampling:** Uses join date as reference point (same as training)
4. **Real-world test:** Tests on completely unseen, real-world data

## Notes

- The data has gaps, especially at the beginning of the collection period
- The 1.2x multiplier is an approximation to compensate for missing days
- Ground truth labels are generated from the same scraped dataset
- This tests the model's ability to generalize to real-world, contemporary data
