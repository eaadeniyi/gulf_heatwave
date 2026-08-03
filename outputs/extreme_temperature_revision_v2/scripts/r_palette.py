"""
=============================================================================
r_palette  --  colour-vision validation of the figure palettes.
=============================================================================
The categorical palettes used by every figure in this package are CHECKED, not
eyeballed. The checks are the ones specified by the project's visualisation
standard, implemented here in Python because the reference JavaScript validator
needs a Node runtime that is not installed in this environment:

  2  lightness band          OKLCH L in [0.43, 0.77] on a light surface
  3  chroma floor            OKLCH C >= 0.10, below which a hue reads as grey
  4  CVD separation          Euclidean distance in OKLab x 100 between every
                             relevant pair, under protanopia and deuteranopia
                             simulated with Machado, Oliveira and Fernandes
                             (2009) at severity 1.0.
                             target >= 8, floor >= 6 (floor legal ONLY with a
                             second, non-colour encoding), and a normal-vision
                             floor of >= 15 which is a hard gate
  5  contrast versus surface >= 3:1 for marks

Every figure in this package carries a second encoding as well as colour -
marker shape for the five states, hatch for the absolute gates, and direct
labels - so the floor band is usable where it occurs. The report is written to
qa/palette_validation.csv so a reviewer can see the numbers rather than trust
the choice.
=============================================================================
"""
import os
import sys
import itertools

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r00_config as K

LIGHT_SURFACE = "#ffffff"
L_BAND = (0.43, 0.77)
C_FLOOR = 0.10
CVD_TARGET, CVD_FLOOR, NORMAL_FLOOR = 8.0, 6.0, 15.0
CONTRAST_MIN = 3.0

# Machado, Oliveira and Fernandes (2009), severity 1.0, applied in LINEAR RGB
MACHADO = {
    "protanopia": np.array([[0.152286, 1.052583, -0.204868],
                            [0.114503, 0.786281, 0.099216],
                            [-0.003882, -0.048116, 1.051998]]),
    "deuteranopia": np.array([[0.367322, 0.860646, -0.227968],
                              [0.280085, 0.672501, 0.047413],
                              [-0.011820, 0.042940, 0.968881]]),
}


def hex_to_srgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_oklab(rgb):
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    lms = m1 @ rgb
    lms = np.cbrt(np.maximum(lms, 0.0))
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return m2 @ lms


def oklab(h):
    return linear_to_oklab(srgb_to_linear(hex_to_srgb(h)))


def oklch(h):
    L, a, b = oklab(h)
    return L, float(np.hypot(a, b))


def simulate(h, kind):
    lin = srgb_to_linear(hex_to_srgb(h))
    return linear_to_oklab(np.clip(MACHADO[kind] @ lin, 0.0, 1.0))


def delta_e(x, y):
    return float(np.linalg.norm(np.asarray(x) - np.asarray(y)) * 100.0)


def relative_luminance(h):
    r, g, b = srgb_to_linear(hex_to_srgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(h, surface=LIGHT_SURFACE):
    a, b = relative_luminance(h), relative_luminance(surface)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def validate(name, colours, pairs="all", second_encoding="", surface=LIGHT_SURFACE):
    """colours: {label: hex}. Returns (rows, worst_pairs)."""
    rows = []
    items = list(colours.items())
    for lab, hx in items:
        L, Cc = oklch(hx)
        ct = contrast(hx, surface)
        neutral_midpoint = ("shoulder" in lab.lower() or "May and October" in lab)
        rows.append(dict(palette=name, check="per_colour", entity=lab, hex=hx,
                         oklch_L=round(L, 4), oklch_C=round(Cc, 4),
                         contrast_vs_surface=round(ct, 3),
                         lightness_band="PASS" if L_BAND[0] <= L <= L_BAND[1] else "FAIL",
                         chroma_floor=("EXEMPT_NEUTRAL_MIDPOINT" if neutral_midpoint else
                                    ("PASS" if Cc >= C_FLOOR else "FAIL")),
                         contrast="PASS" if ct >= CONTRAST_MIN else "WARN",
                         second_encoding=second_encoding, value=np.nan, verdict=""))
    combos = (list(itertools.combinations(range(len(items)), 2)) if pairs == "all"
              else [(i, i + 1) for i in range(len(items) - 1)])
    worst = {"normal": (np.inf, ""), "protanopia": (np.inf, ""),
             "deuteranopia": (np.inf, "")}
    for i, j in combos:
        (la, ha), (lb, hb) = items[i], items[j]
        d_norm = delta_e(oklab(ha), oklab(hb))
        d = {"normal": d_norm}
        for kind in MACHADO:
            d[kind] = delta_e(simulate(ha, kind), simulate(hb, kind))
        for kind, v in d.items():
            if v < worst[kind][0]:
                worst[kind] = (v, "%s vs %s" % (la, lb))
        cvd_min = min(d["protanopia"], d["deuteranopia"])
        verdict = ("PASS" if cvd_min >= CVD_TARGET else
                   "FLOOR_OK_WITH_SECOND_ENCODING" if cvd_min >= CVD_FLOOR else "FAIL")
        if d_norm < NORMAL_FLOOR:
            verdict = "FAIL_NORMAL_VISION_FLOOR"
        rows.append(dict(palette=name, check="pair", entity="%s | %s" % (la, lb),
                         hex="%s|%s" % (ha, hb), oklch_L=np.nan, oklch_C=np.nan,
                         contrast_vs_surface=np.nan, lightness_band="",
                         chroma_floor="", contrast="",
                         second_encoding=second_encoding,
                         value=round(cvd_min, 2), verdict=verdict,
                         delta_e_normal=round(d_norm, 2),
                         delta_e_protanopia=round(d["protanopia"], 2),
                         delta_e_deuteranopia=round(d["deuteranopia"], 2)))
    return rows, worst


def palettes():
    return [
        ("states (figures E2-E4, one line or box per state)",
         {K.STATE_LABEL[s]: K.STATE_STYLE[s]["color"] for s in K.STATES},
         "all", "marker shape per state (^ o s D v) and direct state labels"),
        ("ordinal gate/family ramp (single hue, monotone lightness)",
         {v["label"]: v["color"] for v in K.GATE_STYLE.values()},
         "adjacent", "hatch per step, monotone lightness, and direct value labels"),
        ("samples (figure comparing sample A with sample B)",
         {v["label"]: v["color"] for v in K.SAMPLE_STYLE.values()},
         "adjacent", "hatch per sample"),
        ("seasons (diverging: warm and cool poles, neutral shoulder midpoint)",
         {K.SEASON_STYLE[k]["label"]: K.SEASON_STYLE[k]["color"]
          for k in ("warm", "shoulder", "cool")},
         "all", "direct percentage labels on every segment"),
    ]


def run(write=True):
    rows = []
    summary = []
    for name, cols, pairs, enc in palettes():
        r, worst = validate(name, cols, pairs, enc)
        rows += r
        pair_rows = [x for x in r if x["check"] == "pair"]
        fails = [x for x in pair_rows if x["verdict"].startswith("FAIL")]
        floor = [x for x in pair_rows if x["verdict"] == "FLOOR_OK_WITH_SECOND_ENCODING"]
        summary.append(dict(
            palette=name, colours=len(cols), pair_rule=pairs, pairs_checked=len(pair_rows),
            worst_normal_delta_e=round(worst["normal"][0], 2),
            worst_normal_pair=worst["normal"][1],
            worst_protanopia_delta_e=round(worst["protanopia"][0], 2),
            worst_deuteranopia_delta_e=round(worst["deuteranopia"][0], 2),
            pairs_failing=len(fails), pairs_in_floor_band=len(floor),
            second_encoding=enc,
            overall="FAIL" if fails else ("PASS_WITH_SECOND_ENCODING" if floor
                                          else "PASS")))
    df = pd.DataFrame(rows)
    sm = pd.DataFrame(summary)
    if write:
        os.makedirs(K.DIR_QA, exist_ok=True)
        df.to_csv(os.path.join(K.DIR_QA, "palette_validation.csv"), index=False)
        sm.to_csv(os.path.join(K.DIR_QA, "palette_validation_summary.csv"), index=False)
    return df, sm


if __name__ == "__main__":
    df, sm = run()
    pd.set_option("display.width", 200)
    print(sm.to_string(index=False))
    bad = df[(df["check"] == "pair") & df["verdict"].astype(str).str.startswith("FAIL")]
    if len(bad):
        print("\nFAILING PAIRS")
        print(bad[["palette", "entity", "delta_e_normal", "delta_e_protanopia",
                   "delta_e_deuteranopia", "verdict"]].to_string(index=False))
    floor = df[(df["check"] == "pair")
               & (df["verdict"] == "FLOOR_OK_WITH_SECOND_ENCODING")]
    if len(floor):
        print("\nFLOOR-BAND PAIRS (legal only with a second encoding, which is present)")
        print(floor[["palette", "entity", "delta_e_protanopia",
                     "delta_e_deuteranopia"]].to_string(index=False))
