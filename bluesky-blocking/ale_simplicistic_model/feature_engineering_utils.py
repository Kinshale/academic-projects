"""
Feature Engineering Utilities
Common functions for creating features from user activity vectors.
"""

import pandas as pd
import numpy as np


def first_active_day(vec):
    """Find the first day (0-6) when activity occurred, -1 if none."""
    for i, val in enumerate(vec):
        if val and val > 0:
            return i
    return -1


def last_active_day(vec):
    """Find the last day (0-6) when activity occurred, -1 if none."""
    for i in range(len(vec)-1, -1, -1):
        if vec[i] and vec[i] > 0:
            return i
    return -1


def create_basic_features(df):
    """
    Create basic statistical features from activity vectors.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with activity vector columns (posts_vec, blocks_actor_vec, etc.)
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with added basic feature columns
    """
    df = df.copy()
    
    # Posts features (week 1: days 0..6)
    df['posts_total'] = df['posts_vec'].apply(sum)
    df['posts_avg'] = df['posts_vec'].apply(lambda v: sum(v)/7.0)
    df['posts_active_days'] = df['posts_vec'].apply(lambda v: sum(1 for x in v if x>0))
    df['posts_day0'] = df['posts_vec'].apply(lambda v: int(v[0]))

    # Blocks features (initiated vs received)
    df['blocks_initiated_total'] = df['blocks_actor_vec'].apply(sum)
    df['blocks_received_total'] = df['blocks_subject_vec'].apply(sum)
    df['blocks_initiated_active_days'] = df['blocks_actor_vec'].apply(lambda v: sum(1 for x in v if x>0))
    df['blocks_received_active_days'] = df['blocks_subject_vec'].apply(lambda v: sum(1 for x in v if x>0))

    # Follows features (made vs received)
    df['follows_made_total'] = df['follows_actor_vec'].apply(sum)
    df['follows_received_total'] = df['follows_subject_vec'].apply(sum)
    df['follows_made_active_days'] = df['follows_actor_vec'].apply(lambda v: sum(1 for x in v if x>0))
    df['follows_received_active_days'] = df['follows_subject_vec'].apply(lambda v: sum(1 for x in v if x>0))

    # Likes features (made vs received)
    df['likes_made_total'] = df['likes_actor_vec'].apply(sum)
    df['likes_received_total'] = df['likes_subject_vec'].apply(sum)
    df['likes_made_active_days'] = df['likes_actor_vec'].apply(lambda v: sum(1 for x in v if x>0))
    df['likes_received_active_days'] = df['likes_subject_vec'].apply(lambda v: sum(1 for x in v if x>0))
    
    return df


def create_advanced_features(df):
    """
    Create advanced block-related features (ratios, intensity, interactions).
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with basic features already created
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with added advanced feature columns
    """
    df = df.copy()
    
    # Ratio features (handle division by zero)
    df['blocks_ratio_initiated_received'] = df.apply(
        lambda row: row['blocks_initiated_total'] / row['blocks_received_total'] 
        if row['blocks_received_total'] > 0 else row['blocks_initiated_total'], 
        axis=1
    )

    # Intensity: blocks per active day (how aggressive when active)
    df['blocks_initiated_per_active_day'] = df.apply(
        lambda row: row['blocks_initiated_total'] / row['blocks_initiated_active_days'] 
        if row['blocks_initiated_active_days'] > 0 else 0, 
        axis=1
    )

    # Net balance: initiated minus received (positive = more blocker, negative = more blocked)
    df['blocks_net_balance'] = df['blocks_initiated_total'] - df['blocks_received_total']

    # Interaction features: blocks combined with other activity
    df['blocks_to_posts_ratio'] = df.apply(
        lambda row: row['blocks_initiated_total'] / row['posts_total'] 
        if row['posts_total'] > 0 else row['blocks_initiated_total'], 
        axis=1
    )

    df['blocks_to_follows_ratio'] = df.apply(
        lambda row: row['blocks_initiated_total'] / row['follows_made_total'] 
        if row['follows_made_total'] > 0 else row['blocks_initiated_total'], 
        axis=1
    )
    
    return df


def create_recency_features(df):
    """
    Create temporal/recency features (first/last active day).
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with activity vector columns
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with added recency feature columns
    """
    df = df.copy()
    
    # Posts recency
    df['posts_first_active_day'] = df['posts_vec'].apply(first_active_day)
    df['posts_last_active_day'] = df['posts_vec'].apply(last_active_day)

    # Follows recency (made vs received)
    df['follows_made_first_day'] = df['follows_actor_vec'].apply(first_active_day)
    df['follows_made_last_day'] = df['follows_actor_vec'].apply(last_active_day)

    # Likes recency (made vs received)
    df['likes_made_first_day'] = df['likes_actor_vec'].apply(first_active_day)
    df['likes_made_last_day'] = df['likes_actor_vec'].apply(last_active_day)

    # Blocks recency (initiated vs received)
    df['blocks_initiated_first_day'] = df['blocks_actor_vec'].apply(first_active_day)
    df['blocks_initiated_last_day'] = df['blocks_actor_vec'].apply(last_active_day)

    # Aggregate recency: most recent activity day across types (max of last_day values)
    df['last_active_overall'] = df[['posts_last_active_day', 'follows_made_last_day', 
                                     'likes_made_last_day', 'blocks_initiated_last_day']].max(axis=1)
    
    return df


def create_all_features(df):
    """
    Create all features at once: basic, advanced, and recency.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with activity vector columns
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with all feature columns added
    """
    df = create_basic_features(df)
    df = create_advanced_features(df)
    df = create_recency_features(df)
    return df


def get_all_feature_columns():
    """
    Get list of all feature column names (in order).
    
    Returns:
    --------
    list
        List of feature column names
    """
    return [
        # Basic statistics
        'posts_total', 'posts_avg', 'posts_active_days', 'posts_day0',
        'blocks_initiated_total', 'blocks_received_total', 
        'blocks_initiated_active_days', 'blocks_received_active_days',
        'follows_made_total', 'follows_received_total', 
        'follows_made_active_days', 'follows_received_active_days',
        'likes_made_total', 'likes_received_total', 
        'likes_made_active_days', 'likes_received_active_days',
        
        # Advanced block features
        'blocks_ratio_initiated_received',
        'blocks_initiated_per_active_day',
        'blocks_net_balance',
        'blocks_to_posts_ratio',
        'blocks_to_follows_ratio',
        
        # Recency features
        'posts_first_active_day', 'posts_last_active_day',
        'follows_made_first_day', 'follows_made_last_day',
        'likes_made_first_day', 'likes_made_last_day',
        'blocks_initiated_first_day', 'blocks_initiated_last_day',
        'last_active_overall',
    ]


def select_features_by_correlation(X, y, threshold=0.05, verbose=True):
    """
    Select features based on correlation with target.
    
    Parameters:
    -----------
    X : pd.DataFrame
        Feature matrix
    y : pd.Series
        Target variable
    threshold : float
        Minimum absolute correlation to keep a feature
    verbose : bool
        Whether to print detailed information
        
    Returns:
    --------
    tuple: (list, pd.Series)
        - List of selected feature names
        - Series of correlations for all features
    """
    # Calculate correlations with target
    corr_with_target = X.corrwith(y).abs()
    
    # Filter features
    strong_features = corr_with_target[corr_with_target >= threshold].index.tolist()
    
    if verbose:
        print(f"="*80)
        print(f"FEATURE SELECTION: Correlation-based filtering")
        print(f"="*80)
        print(f"\nCorrelation threshold: {threshold}")
        print(f"Original features: {len(X.columns)}")
        print(f"Strong features (≥ {threshold}): {len(strong_features)}")
        print(f"Removed features: {len(X.columns) - len(strong_features)}")
        
        if len(strong_features) > 0:
            print(f"\n✓ Selected features:")
            for feat in sorted(strong_features, key=lambda x: corr_with_target[x], reverse=True):
                print(f"  - {feat}: {corr_with_target[feat]:.4f}")
        
        removed_features = [f for f in X.columns if f not in strong_features]
        if removed_features:
            print(f"\nRemoved weak features:")
            for feat in removed_features:
                print(f"  - {feat}: {corr_with_target[feat]:.4f}")
    
    if len(strong_features) == 0:
        print("\n⚠️  No features meet the threshold! Returning all features.")
        return list(X.columns), corr_with_target
    
    return strong_features, corr_with_target


def create_bucketed_classes(counts, bins=None, labels=None):
    """
    Convert block counts to bucketed classes.
    
    Parameters:
    -----------
    counts : pd.Series
        Block count series
    bins : list, optional
        Bin edges. Default: [-1, 0, 3, inf] for 0 / 1-3 / 4+
    labels : list, optional
        Class labels. Default: [0, 1, 2]
        
    Returns:
    --------
    pd.Series
        Bucketed classes
    """
    if bins is None:
        bins = [-1, 0, 3, float('inf')]
    if labels is None:
        labels = [0, 1, 2]
    
    return pd.cut(counts, bins=bins, labels=labels).astype(int)
