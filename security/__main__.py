"""Run with python -m security; all operations are local and offline."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .analyzer import analyze
from .baseline import run_baseline
from .checks import audit_fold, check_fit_rows, check_temporal_features, load_manifest
from .data import load_features, sha256, write_json
from .evaluation import align_predictions, evaluate


def provenance(input_path, manifest=None):
    return {"input_name": Path(input_path).name, "input_sha256": sha256(input_path),
            "manifest_sha256": sha256(manifest) if manifest else None,
            "python": sys.version.split()[0],
            "dependencies": {name: importlib.metadata.version(name) for name in ["numpy", "pandas", "pyarrow"]},
            "security_source_sha256": {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}}


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    for command in ["analyze", "audit", "baseline", "evaluate"]:
        p = sub.add_parser(command)
        p.add_argument("--input", type=Path, required=True, help="Existing build_features.py parquet")
        if command != "analyze":
            p.add_argument("--manifest", type=Path, required=True)
        if command == "baseline":
            p.add_argument("--output-dir", type=Path, required=True, help="New directory; must not exist")
        else:
            p.add_argument("--output", type=Path, required=True, help="New JSON file; must not exist")
        if command == "audit":
            p.add_argument("--byte-bin", type=int, default=4)
            p.add_argument("--fail-on-duplicates", action="store_true")
            p.add_argument("--fit-receipt", type=Path, help="JSON with input_sha256 and folds mapping to fit row positions")
        if command == "evaluate":
            p.add_argument("--fold", required=True, help="Manifest name, held_out_vehicle, or fold_N")
            p.add_argument("--predictions", type=Path, required=True,
                           help="CSV with row_position,label_bin,y_pred,input_sha256; optional fold column")
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        target = args.output_dir if args.command == "baseline" else args.output
        if target.exists():
            raise ValueError(f"Output already exists: {target}; choose a new path")
        df = load_features(args.input)
        metadata = provenance(args.input, getattr(args, "manifest", None))
        if args.command == "analyze":
            temporal = check_temporal_features(df)
            write_json(args.output, {"provenance": metadata, "temporal_audit": temporal, **analyze(df)})
            return 0
        manifest, folds = load_manifest(args.manifest, args.input, df)
        metadata["partition_positions_sha256"] = {
            name: {part: hashlib.sha256(np.asarray(rows, dtype="<i8").tobytes()).hexdigest()
                   for part, rows in partitions.items()}
            for name, partitions in folds}
        if args.command == "audit":
            receipt = json.loads(args.fit_receipt.read_text()) if args.fit_receipt else None
            if receipt and receipt.get("input_sha256") != metadata["input_sha256"]:
                raise ValueError("Preprocessing receipt input hash mismatch")
            results = {}
            for name, partitions in folds:
                results[name] = audit_fold(df, partitions, args.byte_bin, args.fail_on_duplicates)
                if receipt is not None:
                    if name not in receipt.get("folds", {}):
                        raise ValueError(f"Missing preprocessing fit receipt for {name}")
                    check_fit_rows(partitions, receipt["folds"][name])
                    results[name]["preprocessing_fit"] = "receipt contains training rows only; receipt is self-reported"
            write_json(args.output, {"provenance": metadata, "feature_contracts": manifest["variants"],
                                     "temporal_audit": check_temporal_features(df), "folds": results})
        elif args.command == "baseline":
            result, exports = run_baseline(df, folds)
            # All validation and computation precede creation; never reuse a result directory.
            args.output_dir.mkdir(parents=True, exist_ok=False)
            result["prediction_exports"] = []
            for number, (name, rule, rows, predictions) in enumerate(exports):
                filename = f"{number:03d}_{rule}.csv"
                exported = pd.DataFrame({"row_position": rows, "label_bin": df.iloc[rows].label_bin.to_numpy(),
                                         "y_pred": predictions, "input_sha256": metadata["input_sha256"],
                                         "fold": name, "rule": rule})
                exported.to_csv(args.output_dir / filename, index=False, mode="x")
                result["prediction_exports"].append({"fold": name, "rule": rule, "file": filename})
            write_json(args.output_dir / "report.json", {"provenance": metadata, **result})
        else:
            matches = [(name, parts) for name, parts in folds if name == args.fold]
            if len(matches) != 1:
                raise ValueError(f"Unknown fold {args.fold!r}; available: {[name for name, _ in folds]}")
            name, partitions = matches[0]
            exported = pd.read_csv(args.predictions)
            if "input_sha256" not in exported or not exported.input_sha256.eq(metadata["input_sha256"]).all():
                raise ValueError("Predictions must identify the exact input_sha256")
            if "fold" in exported and not exported.fold.eq(name).all():
                raise ValueError("Predictions belong to a different fold")
            predictions = align_predictions(df, partitions["test"], exported)
            write_json(args.output, {"provenance": metadata, "fold": name,
                                     "predictions_sha256": sha256(args.predictions),
                                     **evaluate(df.iloc[partitions["test"]], predictions)})
        return 0
    except (ValueError, KeyError, OSError, TypeError) as error:
        cli.exit(2, f"security: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
