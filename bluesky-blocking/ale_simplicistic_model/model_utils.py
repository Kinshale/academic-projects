"""
Model training and evaluation utilities for block prediction.

This module provides reusable functions for:
- Training classifiers (Logistic Regression, Random Forest, Gradient Boosting)
- Evaluating model performance
- Visualizing results (confusion matrices, bar charts)
- Saving/loading models
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
import joblib
import os
from datetime import datetime

# Class labels for block activity
CLASS_LABELS = ['Inactive (0)', 'Low (1-3)', 'High (4+)']
CLASS_LABELS_SHORT = ['Inactive\n(0)', 'Low\n(1-3)', 'High\n(4+)']


def load_data(features_path: str, target_path: str) -> tuple:
    """
    Load and align features and targets from parquet files.
    
    Returns:
        X: Feature DataFrame (without did_id)
        y_loaded: Target DataFrame (with did_id and all target columns)
        feature_cols: List of feature column names
    """
    X_with_id = pd.read_parquet(features_path)
    y_loaded = pd.read_parquet(target_path)
    
    if 'did_id' in X_with_id.columns and 'did_id' in y_loaded.columns:
        # Merge to ensure perfect alignment
        data_aligned = X_with_id.merge(y_loaded, on='did_id', how='inner')
        
        # Extract features (drop did_id and target columns)
        feature_cols = [col for col in X_with_id.columns if col != 'did_id']
        X = data_aligned[feature_cols]
        
        # Get all target columns
        target_cols = [c for c in y_loaded.columns]
        y_loaded = data_aligned[target_cols]
        
        print(f"✓ Features and targets aligned by did_id: {len(X)} samples")
    else:
        print("⚠️  WARNING: No did_id found - features and targets may be misaligned!")
        feature_cols = [col for col in X_with_id.columns if col != 'did_id']
        X = X_with_id[feature_cols] if 'did_id' in X_with_id.columns else X_with_id
    
    return X, y_loaded, feature_cols


def prepare_data(X: pd.DataFrame, y: pd.Series, test_size: float = 0.5, 
                 random_state: int = 42, scale: bool = True) -> dict:
    """
    Split data into train/test and optionally scale features.
    
    Returns:
        Dictionary with train/test splits and scaler
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    
    result = {
        'X_train': X_train,
        'X_test': X_test,
        'y_train': y_train,
        'y_test': y_test,
        'scaler': None,
        'X_train_scaled': None,
        'X_test_scaled': None
    }
    
    if scale:
        scaler = StandardScaler()
        result['X_train_scaled'] = scaler.fit_transform(X_train)
        result['X_test_scaled'] = scaler.transform(X_test)
        result['scaler'] = scaler
    
    print(f"Train/Test split: {X_train.shape} / {X_test.shape}")
    
    return result


def get_model(model_name: str, random_state: int = 42):
    """
    Create a classifier by name.
    
    Args:
        model_name: One of 'LogisticRegression', 'RandomForest', 'GradientBoosting'
        random_state: Random seed for reproducibility
    
    Returns:
        Configured sklearn classifier
    """
    models = {
        'LogisticRegression': LogisticRegression(
            multi_class='multinomial',
            solver='lbfgs',
            max_iter=1000,
            class_weight='balanced',
            random_state=random_state
        ),
        'RandomForest': RandomForestClassifier(
            n_estimators=80,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            random_state=random_state,
            class_weight='balanced',
            n_jobs=-1
        ),
        'GradientBoosting': GradientBoostingClassifier(
            n_estimators=80,
            random_state=random_state
        )
    }
    
    if model_name not in models:
        raise ValueError(f"Unknown model: {model_name}. Choose from {list(models.keys())}")
    
    return models[model_name]


def train_and_evaluate(model_name: str, data: dict, use_scaled: bool = None, 
                       week_label: str = None, verbose: bool = True) -> dict:
    """
    Train a model and compute evaluation metrics.
    
    Args:
        model_name: Name of the model to train
        data: Dictionary from prepare_data()
        use_scaled: Whether to use scaled features (auto-detected if None)
        week_label: Optional label for printing (e.g., 'Week 2')
        verbose: Whether to print results
    
    Returns:
        Dictionary with model, predictions, and metrics
    """
    # Auto-detect scaling: use scaled for LogisticRegression
    if use_scaled is None:
        use_scaled = model_name == 'LogisticRegression'
    
    # Select appropriate data
    if use_scaled and data['X_train_scaled'] is not None:
        X_train = data['X_train_scaled']
        X_test = data['X_test_scaled']
    else:
        X_train = data['X_train']
        X_test = data['X_test']
    
    y_train = data['y_train']
    y_test = data['y_test']
    
    # Create and train model
    model = get_model(model_name)
    model.fit(X_train, y_train)
    
    # Predict
    y_pred = model.predict(X_test)
    
    # Compute metrics
    result = {
        'model': model,
        'y_pred': y_pred,
        'y_test': y_test,
        'accuracy': accuracy_score(y_test, y_pred),
        'f1_macro': f1_score(y_test, y_pred, average='macro'),
        'f1_weighted': f1_score(y_test, y_pred, average='weighted'),
        'f1_per_class': f1_score(y_test, y_pred, average=None),
        'confusion_matrix': confusion_matrix(y_test, y_pred),
        'model_name': model_name
    }
    
    if verbose:
        label = f" ({week_label})" if week_label else ""
        print(f"\n{model_name}{label}:")
        print(f"  Accuracy: {result['accuracy']:.4f}")
        print(f"  Macro F1: {result['f1_macro']:.4f}")
        print(f"  Weighted F1: {result['f1_weighted']:.4f}")
    
    return result


def train_all_models(data: dict, week_label: str = None, verbose: bool = True) -> dict:
    """
    Train all three model types and return results.
    
    Returns:
        Dictionary mapping model names to their results
    """
    results = {}
    model_names = ['LogisticRegression', 'RandomForest', 'GradientBoosting']
    
    if verbose:
        print('='*70)
        print(f'TRAINING ALL MODELS{" - " + week_label if week_label else ""}')
        print('='*70)
    
    for model_name in model_names:
        results[model_name] = train_and_evaluate(
            model_name, data, week_label=week_label, verbose=verbose
        )
    
    if verbose:
        print('\n✓ All models trained')
    
    return results


def print_class_distribution(y: pd.Series, label: str = ""):
    """Print class distribution for a target variable."""
    print(f'\n{label} class distribution:' if label else '\nClass distribution:')
    dist = y.value_counts().sort_index()
    pct = y.value_counts(normalize=True).sort_index() * 100
    for cls in dist.index:
        print(f'  Class {cls}: {dist[cls]:,} samples ({pct[cls]:.1f}%)')


def results_to_dataframe(results: dict, week_label: str = None) -> pd.DataFrame:
    """Convert results dictionary to a DataFrame for easy comparison."""
    rows = []
    for model_name, res in results.items():
        row = {
            'Model': model_name,
            'Accuracy': res['accuracy'],
            'Macro F1': res['f1_macro'],
            'Weighted F1': res['f1_weighted']
        }
        if week_label:
            row['Week'] = week_label
        rows.append(row)
    return pd.DataFrame(rows)


def plot_performance_comparison(results: dict, title: str = "Model Performance"):
    """Create bar chart comparing model performance metrics."""
    perf_df = results_to_dataframe(results)
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    metrics = ['Accuracy', 'Macro F1', 'Weighted F1']
    colors = ['#3498db', '#2ecc71', '#e74c3c']
    
    for idx, metric in enumerate(metrics):
        ax = axes[idx]
        bars = ax.bar(perf_df['Model'], perf_df[metric], color=colors[idx])
        ax.set_title(f'{metric}', fontsize=12, fontweight='bold')
        ax.set_xlabel('Model')
        ax.set_ylabel(metric)
        ax.set_ylim([0, 1.05])
        ax.grid(axis='y', alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}', ha='center', va='bottom', fontsize=10)
    
    plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.show()
    
    # Print best model
    best = max(results.items(), key=lambda x: x[1]['f1_macro'])
    print(f"\n🏆 Best model (by Macro F1): {best[0]} = {best[1]['f1_macro']:.4f}")
    
    return perf_df


def plot_confusion_matrices(results: dict, title: str = "Confusion Matrices"):
    """Plot confusion matrices for all models."""
    n_models = len(results)
    fig, axes = plt.subplots(1, n_models, figsize=(6*n_models, 5))
    
    if n_models == 1:
        axes = [axes]
    
    for idx, (model_name, res) in enumerate(results.items()):
        ax = axes[idx]
        cm = res['confusion_matrix']
        
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax,
                    xticklabels=CLASS_LABELS_SHORT, yticklabels=CLASS_LABELS_SHORT,
                    cbar_kws={'label': 'Count'})
        
        ax.set_title(f'{model_name}\nAcc: {res["accuracy"]:.3f} | F1: {res["f1_macro"]:.3f}',
                     fontsize=11, fontweight='bold')
        ax.set_xlabel('Predicted')
        ax.set_ylabel('True')
    
    plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.show()


def plot_multi_week_comparison(all_results: dict, weeks: list):
    """
    Compare model performance across multiple weeks.
    
    Args:
        all_results: Dict mapping week labels to results dicts
        weeks: List of week labels (e.g., ['Week 2', 'Week 3', 'Week 4'])
    """
    # Build combined dataframe
    dfs = []
    for week in weeks:
        if week in all_results:
            df = results_to_dataframe(all_results[week], week_label=week)
            dfs.append(df)
    
    if not dfs:
        print("No results to compare!")
        return
    
    perf_df = pd.concat(dfs, ignore_index=True)
    
    print('='*70)
    print('MODEL PERFORMANCE ACROSS WEEKS')
    print('='*70)
    print(perf_df.to_string(index=False))
    
    # Create grouped bar charts
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    metrics = ['Accuracy', 'Macro F1', 'Weighted F1']
    model_names = ['LogisticRegression', 'RandomForest', 'GradientBoosting']
    
    for idx, metric in enumerate(metrics):
        ax = axes[idx]
        x = np.arange(len(model_names))
        width = 0.25
        
        for i, week in enumerate(weeks):
            if week in all_results:
                values = [all_results[week][m][metric.lower().replace(' ', '_')] 
                          if metric.lower().replace(' ', '_') in all_results[week][m]
                          else all_results[week][m].get('f1_macro' if 'f1' in metric.lower() else 'accuracy', 0)
                          for m in model_names]
                # Fix: map metric names properly
                if metric == 'Accuracy':
                    values = [all_results[week][m]['accuracy'] for m in model_names]
                elif metric == 'Macro F1':
                    values = [all_results[week][m]['f1_macro'] for m in model_names]
                else:
                    values = [all_results[week][m]['f1_weighted'] for m in model_names]
                
                bars = ax.bar(x + i*width, values, width, label=week, alpha=0.8)
                
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                            f'{height:.2f}', ha='center', va='bottom', fontsize=8)
        
        ax.set_title(metric, fontsize=12, fontweight='bold')
        ax.set_xticks(x + width * (len(weeks)-1) / 2)
        ax.set_xticklabels(['LR', 'RF', 'GB'])
        ax.set_ylim([0, 1.1])
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    return perf_df


def save_models(results: dict, scaler, feature_cols: list, week_label: str,
                model_dir: str = "../data/ale_simplicistic_model/relative/model_ready") -> str:
    """
    Save all models and metadata to disk.
    
    Returns:
        Path to metadata file
    """
    os.makedirs(model_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    week_tag = week_label.lower().replace(' ', '')
    
    print(f'\n{"="*70}')
    print(f'SAVING MODELS - {week_label}')
    print(f'{"="*70}')
    
    model_paths = {}
    for model_name, res in results.items():
        path = os.path.join(model_dir, f"{model_name.lower()}_{week_tag}_{timestamp}.pkl")
        joblib.dump(res['model'], path)
        model_paths[model_name] = {
            'path': path,
            'accuracy': res['accuracy'],
            'f1_macro': res['f1_macro'],
            'f1_weighted': res['f1_weighted']
        }
        print(f"✓ {model_name} saved: {path}")
    
    # Save scaler
    scaler_path = os.path.join(model_dir, f"scaler_{week_tag}_{timestamp}.pkl")
    if scaler is not None:
        joblib.dump(scaler, scaler_path)
        print(f"✓ Scaler saved: {scaler_path}")
    
    # Save metadata
    metadata = {
        'timestamp': timestamp,
        'week': week_label,
        'models': model_paths,
        'scaler_path': scaler_path,
        'feature_columns': feature_cols,
        'classes': [0, 1, 2],
        'class_labels': CLASS_LABELS
    }
    
    metadata_path = os.path.join(model_dir, f"metadata_{week_tag}_{timestamp}.pkl")
    joblib.dump(metadata, metadata_path)
    print(f"✓ Metadata saved: {metadata_path}")
    
    return metadata_path
