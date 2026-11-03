"""Static F00 plots from measured tables and canonical frames."""
import os

import numpy as np

from .normal_profile import RECORDINGS


LABELS = dict(zip(RECORDINGS, ["Preliminary", "Final first round"]))
COLORS = ["#0072B2", "#D55E00"]


def make_plots(df, profile, comparison, output, config):
    # Keep plotting caches local, as well as all experiment outputs.
    os.environ.setdefault("MPLCONFIGDIR", str(output.parent / "matplotlib-cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "font.family": "DejaVu Sans"})
    ids = profile["ids"]
    names = sorted(ids.can_id_hex.unique())
    x = np.arange(len(names))

    def save(fig, name):
        fig.tight_layout(rect=(0, 0, 1, .97) if fig._suptitle else None)
        fig.savefig(output / name, dpi=140, metadata={"Software": "De-CAN F00"})
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 5))
    for i, recording in enumerate(RECORDINGS):
        part = ids[ids.recording_id.eq(recording)].set_index("can_id_hex").reindex(names)
        ax.bar(x + (i - .5) * .4, part.traffic_percent, width=.4, color=COLORS[i], label=LABELS[recording])
    ax.set(xticks=x, xticklabels=names, ylabel="Share of recording frames (%)", xlabel="CAN arbitration ID (hexadecimal)",
           title="Normal CAN traffic share by ID (separate recording denominators)")
    ax.tick_params(axis="x", rotation=90)
    ax.legend(); save(fig, "can_id_frequency.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    groups = ["near_100Hz", "near_50Hz", "near_10Hz", "near_5Hz", "near_1Hz", "unclassified"]
    for i, recording in enumerate(RECORDINGS):
        part = ids[ids.recording_id.eq(recording)]
        grouped = part.groupby("timing_group")
        for ax, vals in zip(axes, [grouped.size().reindex(groups, fill_value=0),
                                  grouped.traffic_percent.sum().reindex(groups, fill_value=0)]):
            ax.bar(np.arange(len(groups)) + (i - .5) * .4, vals, .4, color=COLORS[i], label=LABELS[recording])
            ax.set_xticks(np.arange(len(groups)), [v.replace("near_", "~") for v in groups], rotation=35)
            ax.set_xlabel("Timing group (requires interval concentration)")
    axes[0].set_ylabel("Number of observed IDs"); axes[1].set_ylabel("Share of recording frames (%)")
    axes[0].legend(); fig.suptitle("Timing groups: ID counts and traffic contribution")
    save(fig, "frequency_groups.png")

    representatives = [0x153, 0x260, 0x545, 0x350, 0x0A0, 0x110, 0x018, 0x5A2]
    fig, axes = plt.subplots(4, 2, figsize=(11, 12))
    for ax, cid in zip(axes.flat, representatives):
        intervals = []
        for recording in RECORDINGS:
            group = df[df.recording_id.eq(recording) & df.can_id_dec.eq(cid)]
            delta = np.diff(group.timestamp) * 1000
            intervals.append(delta[delta > 0])
        union = np.concatenate(intervals)
        if len(union):
            edges = np.histogram_bin_edges(union, bins=55)
            for i, values in enumerate(intervals):
                if len(values):
                    ax.hist(values, bins=edges, density=True, histtype="step", linewidth=1.5,
                            color=COLORS[i], label=LABELS[RECORDINGS[i]])
        ax.set(title=f"0x{cid:03X}", xlabel="Same-ID inter-arrival interval (ms)", ylabel="Probability density (1/ms)")
    axes[0, 0].legend(); fig.suptitle("Positive same-ID intervals; all observed values, no cross-recording intervals")
    save(fig, "interarrival_histograms.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 12), sharey=True)
    cmap = plt.get_cmap("viridis").with_extremes(bad="#dddddd")
    for ax, recording in zip(axes, RECORDINGS):
        part = profile["bytes"][profile["bytes"].recording_id.eq(recording)]
        matrix = part.pivot(index="can_id_hex", columns="byte_position", values="change_fraction").reindex(names)
        image = ax.imshow(np.ma.masked_invalid(matrix.to_numpy()), aspect="auto", vmin=0, vmax=1, cmap=cmap)
        ax.set(title=LABELS[recording], xlabel="Byte position (zero-based)", xticks=np.arange(8),
               yticks=x, yticklabels=names)
    axes[0].set_ylabel("CAN ID (hexadecimal)")
    fig.suptitle("Payload-byte changes: gray = absent or no comparable pair")
    # Reserve a separate legend axis; do not shrink panels and then reposition
    # them over a colorbar created by automatic layout.
    fig.subplots_adjust(left=.09, right=.80, bottom=.06, top=.94, wspace=.18)
    color_axis = fig.add_axes([.84, .20, .025, .60])
    fig.colorbar(image, cax=color_axis, label="Fraction of comparable consecutive pairs with a changed byte")
    fig.savefig(output / "payload_byte_variability.png", dpi=140, metadata={"Software": "De-CAN F00"}); plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(13, 12), sharey=True)
    comp = comparison.set_index("can_id_hex").reindex(names)
    for ax, metric, title in zip(axes, ["rate_recording_fps", "interval_median_ms", "consecutive_repeat_percent"],
                                 ["Average rate (frames/s)", "Median interval (ms; log scale)", "Consecutive repeats (%)"]):
        for i, short in enumerate(["preliminary", "final_1st"]):
            ax.scatter(comp[f"{short}_{metric}"], x + (i - .5) * .2, s=15,
                       color=COLORS[i], label=LABELS[RECORDINGS[i]], marker="o" if i == 0 else "x")
        ax.set(yticks=x, yticklabels=names, xlabel=title)
        ax.grid(axis="x", alpha=.2)
    axes[0].set_ylabel("CAN ID (hexadecimal)"); axes[1].set_xscale("log"); axes[0].legend(loc="lower right")
    axes[0].invert_yaxis(); fig.suptitle("Every observed ID: measured rate, timing and payload repetition")
    save(fig, "recording_comparison.png")

    fig, axes = plt.subplots(len(config["important_ids"]), 2, figsize=(12, 11))
    for row, cid in enumerate(config["important_ids"]):
        name = f"0x{cid:03X}"
        for i, recording in enumerate(RECORDINGS):
            byte = profile["bytes"][(profile["bytes"].recording_id.eq(recording)) & profile["bytes"].can_id_hex.eq(name)]
            axes[row, 0].plot(byte.byte_position, byte.change_fraction, "o-", color=COLORS[i], label=LABELS[recording])
            group = df[df.recording_id.eq(recording) & df.can_id_dec.eq(cid)].head(100)
            axes[row, 1].plot(np.arange(len(group)), group.byte_7, linewidth=1, color=COLORS[i], label=LABELS[recording])
        axes[row, 0].set(title=name, xlabel="Byte position (zero-based)", ylabel="Byte change fraction", ylim=(-.03, 1.03), xticks=np.arange(8))
        axes[row, 1].set(title=f"{name}: raw byte 7, first 100 same-ID frames", xlabel="Message index within this ID", ylabel="Raw byte value (0–255)")
    axes[0, 0].legend(); save(fig, "important_ids.png")
