"""
=============================================================================
r_figlib  --  shared figure furniture and the figure manifest.
=============================================================================
Every figure in this package must be reproducible from a saved table and a
script, and must declare what it does and does not support. `spec()` records
that declaration; the entries are concatenated into
tables/figure_data_manifest.csv by r12.
=============================================================================
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K

SPECS = []


def spec(figure_id, filename, purpose, unit_of_analysis, input_table,
         aggregation, denominator, supports, does_not_support, caption,
         limitation):
    SPECS.append(dict(figure_id=figure_id, figure_file=filename, purpose=purpose,
                      unit_of_analysis=unit_of_analysis, input_table=input_table,
                      aggregation_formula=aggregation, denominator=denominator,
                      result_supported=supports,
                      result_not_supported=does_not_support,
                      draft_caption=caption, limitation=limitation))


def write_specs(path):
    import pandas as pd
    pd.DataFrame(SPECS).to_csv(path, index=False)
    return len(SPECS)


def tidy(ax, grid_axis="y"):
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(axis=grid_axis, color=K.COLOR_GRID, lw=0.6, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#999999")
    ax.tick_params(colors=K.COLOR_INK_SOFT, labelsize=8)
    return ax


def savefig(fig, name):
    p = os.path.join(K.DIR_FIG, name)
    fig.savefig(p, bbox_inches="tight", facecolor="white", dpi=140)
    plt.close(fig)
    K.log("      -> figures/%s" % name)
    return p


def footnote(fig, text, y=0.004):
    fig.text(0.005, y, text, fontsize=6.8, color=K.COLOR_INK_SOFT, va="bottom",
             wrap=True)


def title(fig, main, sub=None, y=1.0):
    fig.suptitle(main, fontsize=13, fontweight="bold", y=y, x=0.005, ha="left")
    if sub:
        fig.text(0.005, y - 0.035, sub, fontsize=9.5, color=K.COLOR_INK, ha="left",
                 va="top")


def warm_season_band(ax, label=True, x0=5.5, x1=9.5):
    """The prespecified warm season, shaded IDENTICALLY wherever it appears."""
    ax.axvspan(x0, x1, color="#c0392b", alpha=0.06, zorder=0)
    if label:
        lo, hi = ax.get_ylim()
        ax.text((x0 + x1) / 2.0, hi, K.SEASON_LABEL["warm"], ha="center", va="top",
                fontsize=7.5, color="#8a2f24")


def state_line(ax, x, y, state, **kw):
    st = K.STATE_STYLE[state]
    return ax.plot(x, y, color=st["color"], marker=st["marker"],
                   markeredgecolor=st["edge"], markeredgewidth=0.6,
                   label=st["label"], **kw)


def label_series_ends(ax, entries, fontsize=7.5, min_gap_frac=0.045):
    """Direct labels at the right-hand end of each series, nudged apart.

    `entries` is a list of (state, x_last, y_last). Labels within min_gap_frac of
    the axis height are spread vertically so five states never overprint.
    """
    entries = [e for e in entries if e[1] is not None and np.isfinite(e[2])]
    if not entries:
        return
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * min_gap_frac
    entries.sort(key=lambda e: e[2])
    placed = []
    for state, xl, yl in entries:
        y = yl
        if placed and y - placed[-1] < gap:
            y = placed[-1] + gap
        placed.append(y)
        st = K.STATE_STYLE[state]
        ax.annotate(state, xy=(xl, yl), xytext=(6, 0), textcoords="offset points",
                    fontsize=fontsize, color=st["edge"], fontweight="bold",
                    va="center", annotation_clip=False)
        if abs(y - yl) > 1e-9:
            ax.annotate(state, xy=(xl, yl), xytext=(xl, y), textcoords="data",
                        fontsize=0, color="none")


def label_last(ax, x, y, state, dx=0.15, fontsize=7.5):
    """Single direct label at the end of one series."""
    x, y = list(x), list(y)
    if not x:
        return
    st = K.STATE_STYLE[state]
    ax.annotate(state, xy=(x[-1], y[-1]), xytext=(6, 0), textcoords="offset points",
                fontsize=fontsize, color=st["edge"], fontweight="bold", va="center",
                annotation_clip=False)
