"""Frame-label metrics with explicit supports and undefined denominators."""
import numpy as np
import pandas as pd


def binary_metrics(truth, predictions):
    truth, predictions = np.asarray(truth), np.asarray(predictions)
    if truth.ndim != 1 or predictions.shape != truth.shape or not len(truth):
        raise ValueError("Expected nonempty, equally sized one-dimensional labels and predictions")
    if not np.isin(truth, [0, 1]).all() or not np.isin(predictions, [0, 1]).all():
        raise ValueError("Truth and predictions must be binary; threshold scores before evaluation")
    tn = int(((truth == 0) & (predictions == 0)).sum())
    fp = int(((truth == 0) & (predictions == 1)).sum())
    fn = int(((truth == 1) & (predictions == 0)).sum())
    tp = int(((truth == 1) & (predictions == 1)).sum())
    def ratio(a, b):
        return a / b if b else None
    return {"rows": len(truth), "regular_support": tn + fp, "attack_support": tp + fn,
            "attack_precision": ratio(tp, tp + fp), "attack_recall": ratio(tp, tp + fn),
            "attack_f1": ratio(2 * tp, 2 * tp + fp + fn),
            "false_positive_rate": ratio(fp, fp + tn), "false_negative_rate": ratio(fn, fn + tp),
            "confusion_matrix": [[tn, fp], [fn, tp]]}


def evaluate(df, predictions):
    """Predictions must already be aligned to df; grouping uses trace context."""
    result = {"overall": binary_metrics(df.label_bin, predictions), "groups": {},
              "semantics": "Frame R/T target; attack_type is recording context, not an injected-frame subtype. "
                           "Rows/columns of confusion matrix are truth/prediction in [regular, attack] order. "
                           "Undefined metrics are null; no trace detection or latency claim is made."}
    grouping = [column for column in ["attack_type", "vehicle", "round", "recording_id", "session_id"] if column in df]
    work = df[["label_bin", *grouping]].reset_index(drop=True).copy()
    work["_prediction"] = np.asarray(predictions)
    for column in grouping:
        result["groups"][column] = {
            str(key): binary_metrics(group.label_bin, group._prediction)
            for key, group in work.groupby(column, sort=True, dropna=False)}
    return result


def align_predictions(df, positions, exported):
    """Join on canonical input row positions, never on CSV order or timestamps."""
    required = {"row_position", "label_bin", "y_pred"}
    if not required.issubset(exported.columns):
        raise ValueError(f"Prediction export requires {sorted(required)}")
    rows = exported.row_position
    if not pd.api.types.is_integer_dtype(rows) or rows.isna().any() or rows.duplicated().any():
        raise ValueError("Prediction row_position must be unique integers")
    if set(rows) != set(positions):
        raise ValueError("Prediction rows do not exactly match this fold's evaluation partition")
    aligned = exported.set_index("row_position").loc[positions]
    if not np.array_equal(aligned.label_bin.to_numpy(), df.iloc[positions].label_bin.to_numpy()):
        raise ValueError("Exported ground truth disagrees with canonical labels")
    binary_metrics(aligned.label_bin, aligned.y_pred)
    return aligned.y_pred.to_numpy(dtype=np.uint8)
