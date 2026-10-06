"""
question_A/my_metrics.py   (Level 2: NumPy only, no scikit-learn)

Precision, recall and F1 written from the definitions.
    precision = TP / (TP + FP)
    recall    = TP / (TP + FN)
    F1        = 2 * precision * recall / (precision + recall)
When a denominator is 0 the metric is defined as 0.0 (same as scikit-learn's
zero_division=0).
"""
import numpy as np


def confusion_counts(y_true, y_pred):
    y_true = np.asarray(y_true).astype(bool)
    y_pred = np.asarray(y_pred).astype(bool)
    tp = int(np.sum(y_true & y_pred))
    fp = int(np.sum(~y_true & y_pred))
    fn = int(np.sum(y_true & ~y_pred))
    tn = int(np.sum(~y_true & ~y_pred))
    return tp, fp, fn, tn


def precision_recall_f1(y_true, y_pred):
    tp, fp, fn, _ = confusion_counts(y_true, y_pred)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1
