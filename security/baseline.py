"""Small CAN-ID shortcut rules on existing recording-safe experiment manifests."""
import numpy as np

from .checks import check_partitions
from .evaluation import evaluate


def id_rules(train, test):
    """Fit only on train: metadata, time, DLC and payload never enter predictions."""
    if not train.label_bin.eq(0).any():
        raise ValueError("Unseen-regular-ID rule needs regular training frames")
    regular_ids = set(train.loc[train.label_bin.eq(0), "can_id_dec"])
    attack_fraction = train.groupby("can_id_dec").label_bin.mean()
    return {
        "zero_id": test.can_id_dec.eq(0).to_numpy(dtype=np.uint8),
        "unseen_regular_id": (~test.can_id_dec.isin(regular_ids)).to_numpy(dtype=np.uint8),
        "id_majority": test.can_id_dec.map(attack_fraction).fillna(0).ge(0.5).to_numpy(dtype=np.uint8),
    }


def run_baseline(df, folds):
    results, exports = {}, []
    for name, partitions in folds:
        partitions = check_partitions(df, partitions)
        train, test = df.iloc[partitions["train"]], df.iloc[partitions["test"]]
        rules = id_rules(train, test)
        results[name] = {rule: evaluate(test, predictions) for rule, predictions in rules.items()}
        for rule, predictions in rules.items():
            exports.append((name, rule, partitions["test"], predictions))
    return {"purpose": "Security shortcut experiment; no replacement for the existing decision-tree ablation.",
            "rules": {"zero_id": "Fixed ID == 0; chosen from existing repository findings, not tuned on these folds.",
                      "unseen_regular_id": "ID absent from regular training frames; no vehicle input.",
                      "id_majority": "Training attack fraction per ID >= 0.5; unknown IDs predict regular."},
            "folds": results}, exports
