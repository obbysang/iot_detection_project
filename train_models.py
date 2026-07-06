#!/usr/bin/env python3
"""
IoT Ransomware Detection - Model Training & Evaluation
Trains Random Forest and Isolation Forest models with comprehensive evaluation

Requirements: pandas, numpy, scikit-learn, matplotlib, seaborn
Run: python3 train_models.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pickle
import json
from pathlib import Path
from datetime import datetime

from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import (
    confusion_matrix, classification_report, roc_auc_score, 
    f1_score, precision_recall_curve, roc_curve, auc
)

# Configuration
DATASET_CSV = "data/iot_labeled_dataset.csv"
MODELS_DIR = "ml_models"
RESULTS_FILE = f"{MODELS_DIR}/evaluation_results.json"

# Ensure models directory exists
Path(MODELS_DIR).mkdir(exist_ok=True)

# Set random seeds for reproducibility
np.random.seed(42)
import random
random.seed(42)

class RansomwareDetector:
    """Complete pipeline for ransomware detection model training and evaluation"""
    
    def __init__(self, dataset_path):
        self.dataset_path = dataset_path
        self.df = None
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.scaler = StandardScaler()
        self.models = {}
        self.results = {}
        
    def load_data(self):
        """Load and prepare dataset"""
        print("[*] Loading dataset...")
        self.df = pd.read_csv(self.dataset_path)
        print(f"[+] Loaded {len(self.df)} flows")
        
        # Display class distribution
        print(f"\nClass distribution:")
        print(self.df['label_name'].value_counts())
        
    def prepare_features(self):
        """Extract features and split data"""
        print("\n[*] Preparing features...")
        
        # Exclude non-feature columns
        exclude_cols = ['src_ip', 'dst_ip', 'label', 'label_name', 'label_reason']
        feature_cols = [c for c in self.df.columns if c not in exclude_cols]
        
        print(f"[+] Using {len(feature_cols)} features:")
        for i, col in enumerate(feature_cols, 1):
            print(f"    {i:2d}. {col}")
        
        X = self.df[feature_cols].values
        y = self.df['label'].values
        
        # Train/test split (80/20 with stratification)
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Normalize features
        self.X_train = self.scaler.fit_transform(self.X_train)
        self.X_test = self.scaler.transform(self.X_test)
        
        print(f"[+] Training set: {len(self.X_train)} samples")
        print(f"[+] Test set: {len(self.X_test)} samples")
        
        return feature_cols
    
    def train_random_forest(self, feature_cols):
        """Train Random Forest classifier"""
        print("\n[*] Training Random Forest...")
        
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
            verbose=0
        )
        
        model.fit(self.X_train, self.y_train)
        self.models['random_forest'] = model
        self.results['random_forest'] = {}
        
        # Predictions
        y_pred = model.predict(self.X_test)
        y_pred_proba = model.predict_proba(self.X_test)[:, 1]
        
        # Evaluation metrics
        cm = confusion_matrix(self.y_test, y_pred)
        f1 = f1_score(self.y_test, y_pred)
        auc_score = roc_auc_score(self.y_test, y_pred_proba)
        
        # Detailed metrics
        tn, fp, fn, tp = cm.ravel()
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
        detection_rate = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        self.results['random_forest'] = {
            'confusion_matrix': cm.tolist(),
            'f1_score': float(f1),
            'roc_auc': float(auc_score),
            'true_positives': int(tp),
            'false_positives': int(fp),
            'true_negatives': int(tn),
            'false_negatives': int(fn),
            'false_positive_rate': float(fpr),
            'false_negative_rate': float(fnr),
            'detection_rate': float(detection_rate),
            'precision': float(tp / (tp + fp)) if (tp + fp) > 0 else 0,
            'recall': float(tp / (tp + fn)) if (tp + fn) > 0 else 0,
        }
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        self.results['random_forest']['top_features'] = feature_importance.head(5).to_dict('records')
        
        # Print results
        print(f"[+] F1 Score: {f1:.4f}")
        print(f"[+] ROC-AUC: {auc_score:.4f}")
        print(f"[+] Detection Rate: {detection_rate:.4f}")
        print(f"[+] False Positive Rate: {fpr:.4f}")
        print(f"\nConfusion Matrix:")
        print(f"  TN={tn:3d}  FP={fp:3d}")
        print(f"  FN={fn:3d}  TP={tp:3d}")
        
        print(f"\nTop 5 Important Features:")
        for idx, row in feature_importance.head(5).iterrows():
            print(f"  {row['feature']:25s}: {row['importance']:.4f}")
        
        # Store predictions for later use
        self.results['random_forest']['y_pred'] = y_pred.tolist()
        self.results['random_forest']['y_pred_proba'] = y_pred_proba.tolist()
        
        return model, feature_importance
    
    def train_isolation_forest(self):
        """Train Isolation Forest for anomaly detection"""
        print("\n[*] Training Isolation Forest (unsupervised)...")
        
        model = IsolationForest(
            contamination=0.15,  # Assume 15% anomalies
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(self.X_train)
        
        # Predictions (-1 for anomalies, 1 for normal)
        y_pred_raw = model.predict(self.X_test)
        y_pred = (y_pred_raw == -1).astype(int)  # Convert to 0/1
        
        # Anomaly scores (higher = more anomalous)
        y_scores = -model.score_samples(self.X_test)
        
        self.models['isolation_forest'] = model
        self.results['isolation_forest'] = {}
        
        # Evaluation metrics
        cm = confusion_matrix(self.y_test, y_pred)
        f1 = f1_score(self.y_test, y_pred)
        auc_score = roc_auc_score(self.y_test, y_scores)
        
        # Detailed metrics
        tn, fp, fn, tp = cm.ravel()
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
        detection_rate = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        self.results['isolation_forest'] = {
            'confusion_matrix': cm.tolist(),
            'f1_score': float(f1),
            'roc_auc': float(auc_score),
            'true_positives': int(tp),
            'false_positives': int(fp),
            'true_negatives': int(tn),
            'false_negatives': int(fn),
            'false_positive_rate': float(fpr),
            'false_negative_rate': float(fnr),
            'detection_rate': float(detection_rate),
            'precision': float(tp / (tp + fp)) if (tp + fp) > 0 else 0,
            'recall': float(tp / (tp + fn)) if (tp + fn) > 0 else 0,
        }
        
        # Print results
        print(f"[+] F1 Score: {f1:.4f}")
        print(f"[+] ROC-AUC: {auc_score:.4f}")
        print(f"[+] Detection Rate: {detection_rate:.4f}")
        print(f"[+] False Positive Rate: {fpr:.4f}")
        print(f"\nConfusion Matrix:")
        print(f"  TN={tn:3d}  FP={fp:3d}")
        print(f"  FN={fn:3d}  TP={tp:3d}")
        
        # Store predictions
        self.results['isolation_forest']['y_pred'] = y_pred.tolist()
        self.results['isolation_forest']['y_scores'] = y_scores.tolist()
        
        return model
    
    def save_models(self):
        """Save trained models to disk"""
        print("\n[*] Saving models...")
        
        for model_name, model in self.models.items():
            path = f"{MODELS_DIR}/{model_name}.pkl"
            with open(path, 'wb') as f:
                pickle.dump(model, f)
            print(f"[+] Saved: {path}")
        
        # Save scaler
        with open(f"{MODELS_DIR}/scaler.pkl", 'wb') as f:
            pickle.dump(self.scaler, f)
        print(f"[+] Saved: {MODELS_DIR}/scaler.pkl")
    
    def visualize_results(self, feature_importance=None):
        """Generate visualizations"""
        print("\n[*] Generating visualizations...")
        
        # Confusion matrices
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        
        cm_rf = np.array(self.results['random_forest']['confusion_matrix'])
        sns.heatmap(cm_rf, annot=True, fmt='d', ax=axes[0], cmap='Blues', cbar=False)
        axes[0].set_title('Random Forest\nConfusion Matrix', fontsize=12, fontweight='bold')
        axes[0].set_ylabel('True Label')
        axes[0].set_xlabel('Predicted Label')
        axes[0].set_xticklabels(['Normal', 'Malicious'])
        axes[0].set_yticklabels(['Normal', 'Malicious'])
        
        cm_iso = np.array(self.results['isolation_forest']['confusion_matrix'])
        sns.heatmap(cm_iso, annot=True, fmt='d', ax=axes[1], cmap='Oranges', cbar=False)
        axes[1].set_title('Isolation Forest\nConfusion Matrix', fontsize=12, fontweight='bold')
        axes[1].set_ylabel('True Label')
        axes[1].set_xlabel('Predicted Label')
        axes[1].set_xticklabels(['Normal', 'Malicious'])
        axes[1].set_yticklabels(['Normal', 'Malicious'])
        
        plt.tight_layout()
        plt.savefig(f'{MODELS_DIR}/01_confusion_matrices.png', dpi=300, bbox_inches='tight')
        print(f"[+] Saved: {MODELS_DIR}/01_confusion_matrices.png")
        plt.close()
        
        # Feature importance
        if feature_importance is not None:
            plt.figure(figsize=(10, 6))
            top_features = feature_importance.head(10)
            plt.barh(range(len(top_features)), top_features['importance'].values)
            plt.yticks(range(len(top_features)), top_features['feature'].values)
            plt.xlabel('Importance', fontweight='bold')
            plt.title('Top 10 Features for Ransomware Detection\n(Random Forest)', fontsize=12, fontweight='bold')
            plt.tight_layout()
            plt.savefig(f'{MODELS_DIR}/02_feature_importance.png', dpi=300, bbox_inches='tight')
            print(f"[+] Saved: {MODELS_DIR}/02_feature_importance.png")
            plt.close()
        
        # ROC curves
        y_pred_proba_rf = np.array(self.results['random_forest']['y_pred_proba'])
        y_scores_iso = np.array(self.results['isolation_forest']['y_scores'])
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        fpr_rf, tpr_rf, _ = roc_curve(self.y_test, y_pred_proba_rf)
        auc_rf = auc(fpr_rf, tpr_rf)
        ax.plot(fpr_rf, tpr_rf, label=f'Random Forest (AUC={auc_rf:.3f})', linewidth=2)
        
        fpr_iso, tpr_iso, _ = roc_curve(self.y_test, y_scores_iso)
        auc_iso = auc(fpr_iso, tpr_iso)
        ax.plot(fpr_iso, tpr_iso, label=f'Isolation Forest (AUC={auc_iso:.3f})', linewidth=2)
        
        ax.plot([0, 1], [0, 1], 'k--', label='Random Classifier', linewidth=1)
        ax.set_xlabel('False Positive Rate', fontweight='bold')
        ax.set_ylabel('True Positive Rate', fontweight='bold')
        ax.set_title('ROC Curves - Ransomware Detection Models', fontsize=12, fontweight='bold')
        ax.legend(loc='lower right', fontsize=10)
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f'{MODELS_DIR}/03_roc_curves.png', dpi=300, bbox_inches='tight')
        print(f"[+] Saved: {MODELS_DIR}/03_roc_curves.png")
        plt.close()
        
        # Model comparison
        models_to_compare = ['random_forest', 'isolation_forest']
        metrics = ['f1_score', 'roc_auc', 'detection_rate', 'false_positive_rate']
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        axes = axes.flatten()
        
        for idx, metric in enumerate(metrics):
            values = [self.results[model][metric] for model in models_to_compare]
            colors = ['#1f77b4', '#ff7f0e']
            axes[idx].bar(models_to_compare, values, color=colors)
            axes[idx].set_title(metric.replace('_', ' ').title(), fontweight='bold')
            axes[idx].set_ylim([0, 1] if metric != 'false_positive_rate' else [0, max(values) + 0.1])
            axes[idx].set_ylabel('Score')
            for i, v in enumerate(values):
                axes[idx].text(i, v + 0.02, f'{v:.3f}', ha='center', fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(f'{MODELS_DIR}/04_model_comparison.png', dpi=300, bbox_inches='tight')
        print(f"[+] Saved: {MODELS_DIR}/04_model_comparison.png")
        plt.close()
    
    def save_results(self):
        """Save results to JSON"""
        print("\n[*] Saving results...")
        
        results_output = {
            'timestamp': datetime.now().isoformat(),
            'dataset_size': len(self.df),
            'train_test_split': '80/20',
            'models': self.results
        }
        
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results_output, f, indent=2)
        
        print(f"[+] Saved: {RESULTS_FILE}")
    
    def print_summary(self):
        """Print final summary"""
        print("\n" + "=" * 70)
        print("TRAINING COMPLETE - SUMMARY")
        print("=" * 70)
        
        print("\n[Random Forest]")
        print(f"  F1 Score:            {self.results['random_forest']['f1_score']:.4f}")
        print(f"  ROC-AUC:             {self.results['random_forest']['roc_auc']:.4f}")
        print(f"  Detection Rate:      {self.results['random_forest']['detection_rate']:.4f}")
        print(f"  False Positive Rate: {self.results['random_forest']['false_positive_rate']:.4f}")
        
        print("\n[Isolation Forest]")
        print(f"  F1 Score:            {self.results['isolation_forest']['f1_score']:.4f}")
        print(f"  ROC-AUC:             {self.results['isolation_forest']['roc_auc']:.4f}")
        print(f"  Detection Rate:      {self.results['isolation_forest']['detection_rate']:.4f}")
        print(f"  False Positive Rate: {self.results['isolation_forest']['false_positive_rate']:.4f}")
        
        print("\n[Deliverables]")
        print(f"  Models saved to:     {MODELS_DIR}/")
        print(f"  Results saved to:    {RESULTS_FILE}")
        print(f"  Visualizations:      4 PNG files in {MODELS_DIR}/")
        
        print("\n[Next Steps]")
        print("  1. Review visualizations in ml_models/")
        print("  2. Use results in your report")
        print("  3. Include confusion matrices and ROC curves")
        print("  4. Discuss feature importance findings")
        print("=" * 70 + "\n")

def main():
    print("=" * 70)
    print("IoT Ransomware Detection - Model Training Pipeline")
    print("=" * 70)
    
    detector = RansomwareDetector(DATASET_CSV)
    
    # Load data
    detector.load_data()
    
    # Prepare features
    feature_cols = detector.prepare_features()
    
    # Train models
    rf_model, feature_importance = detector.train_random_forest(feature_cols)
    iso_model = detector.train_isolation_forest()
    
    # Save models
    detector.save_models()
    
    # Visualize
    detector.visualize_results(feature_importance)
    
    # Save results
    detector.save_results()
    
    # Print summary
    detector.print_summary()

if __name__ == "__main__":
    main()
