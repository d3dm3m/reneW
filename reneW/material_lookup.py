# material_lookup.py
# Helper to select (mu, sigma) from parameters.json based on:
#   domain ('water' or 'sewer'),
#   subtype ('spill' or 'storm' for sewer; ignored for water),
#   material name (any common Swedish/English alias),
#   construction year (to pick correct split, e.g. segjärn <1980/≥1980).

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import json
import unicodedata

@dataclass(frozen=True)
class MaterialParams:
    mu: float
    sigma: float

def load_parameters(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def _norm(s: str) -> str:
    return _strip_accents(s).lower().strip()

# Water split thresholds (from Water workbook: Gråjärn=1950, Segjärn=1980, PVC=1970). [1](https://sbvt-my.sharepoint.com/personal/marcus_nordlander_sbvt_se/_layouts/15/download.aspx?UniqueId=dc881595-1d9e-4d39-a863-99b40fa55d1b&Translate=false&tempauth=v1.eyJzaXRlaWQiOiJiMjEzNzkyNi1hOTQ5LTRjYzktYjZkNS03YzkxNTgxOGM3YTkiLCJhcHBfZGlzcGxheW5hbWUiOiJPZmZpY2UgMzY1IFNlYXJjaCBTZXJ2aWNlIiwiYXBwaWQiOiI2NmE4ODc1Ny0yNThjLTRjNzItODkzYy0zZThiZWQ0ZDY4OTkiLCJhdWQiOiIwMDAwMDAwMy0wMDAwLTBmZjEtY2UwMC0wMDAwMDAwMDAwMDAvc2J2dC1teS5zaGFyZXBvaW50LmNvbUAxYzgzMjVkMy1lMGEyLTQ5M2QtYjg4Mi1iMDhhNmJkOWE3MWUiLCJleHAiOiIxNzU1MTc5NzExIn0.CkAKDGVudHJhX2NsYWltcxIwQ05LMjk4UUdFQUFhRm05bFNtTk1la1UzVmtWSFlXSnlkRjlOZGsxQ1FVRXFBQT09CjIKCmFjdG9yYXBwaWQSJDAwMDAwMDAzLTAwMDAtMDAwMC1jMDAwLTAwMDAwMDAwMDAwMAoKCgRzbmlkEgI2NBILCJDGkeb6zq0-EAUaCzIwLjIwLjMyLjk2Kixpc2didDhMbkJCM2ZLNUtqYUJ6c3N0enBhYUFJb2gvNEIyZW5HeGhIcXprPTCZATgBQhChu60uTrAA0MYtEoxKedNOShBoYXNoZWRwcm9vZnRva2VuUhJbImttc2kiLCJkdmNfY21wIl1qJDAwMjE0Yjg5LThiOWItZDk1ZC0xNWUxLTVhNjQwNGYyMGY2M3IpMGguZnxtZW1iZXJzaGlwfDEwMDMyMDAyOTg3Y2NkZWNAbGl2ZS5jb216ATKCARIJ0yWDHKLgPUkRuIKwimvZpx6SAQZNYXJjdXOaAQpOb3JkbGFuZGVyogEZbWFyY3VzLm5vcmRsYW5kZXJAc2J2dC5zZaoBEDEwMDMyMDAyOTg3Q0NERUOyAU1jb250YWluZXIuc2VsZWN0ZWQgYWxsZmlsZXMud3JpdGUgbXlmaWxlcy53cml0ZSBteWZpbGVzLnJlYWQgYWxscHJvZmlsZXMucmVhZMgBAQ.9cwiU9uSVMbg_zbKgexIMrBrJJe0dJGtj0BtnSrSRMA&ApiVersion=2.0&web=1)
WATER_THRESHOLD = {
    "grajarn": [("grajarn_<1950", None, 1950), ("grajarn_>=1950", 1950, None)],
    "segjarn": [("segjarn_<1980", None, 1980), ("segjarn_>=1980", 1980, None)],
    "pvc":     [("pvc_<1970", None, 1970), ("pvc_>=1970", 1970, None)],
}

# Common aliases for water materials
WATER_ALIASES = {
    "grajarn": {"gråjärn", "grajarn", "gjutjärn", "gjutjarn", "grey iron", "cast iron"},
    "segjarn": {"segjärn", "segjarn", "ductile iron", "nodular iron", "dci", "sgi", "sgj"},
    "pe":      {"pe", "polyeten", "polyethylene", "hdpe", "ldpe"},
    "pvc":     {"pvc", "polyvinylklorid", "polyvinyl chloride"},
    "ovrigt":  {"övrigt", "ovrigt", "okänt", "okant", "unknown", "other", "misc", "diverse"}
}

# Sewer aliases (Avlopp). Spill uses Betong <1950 / 1950–1969 / ≥1970; Storm uses Betong <1950 / 1950–1969 only. [2](https://sbvt-my.sharepoint.com/personal/marcus_nordlander_sbvt_se/_layouts/15/download.aspx?UniqueId=3000430b-cc55-45b6-9ad1-fedb7dae09e2&Translate=false&tempauth=v1.eyJzaXRlaWQiOiJiMjEzNzkyNi1hOTQ5LTRjYzktYjZkNS03YzkxNTgxOGM3YTkiLCJhcHBfZGlzcGxheW5hbWUiOiJPZmZpY2UgMzY1IFNlYXJjaCBTZXJ2aWNlIiwiYXBwaWQiOiI2NmE4ODc1Ny0yNThjLTRjNzItODkzYy0zZThiZWQ0ZDY4OTkiLCJhdWQiOiIwMDAwMDAwMy0wMDAwLTBmZjEtY2UwMC0wMDAwMDAwMDAwMDAvc2J2dC1teS5zaGFyZXBvaW50LmNvbUAxYzgzMjVkMy1lMGEyLTQ5M2QtYjg4Mi1iMDhhNmJkOWE3MWUiLCJleHAiOiIxNzU1MTc5NzEyIn0.CkAKDGVudHJhX2NsYWltcxIwQ05LMjk4UUdFQUFhRm05bFNtTk1la1UzVmtWSFlXSnlkRjlOZGsxQ1FVRXFBQT09CjIKCmFjdG9yYXBwaWQSJDAwMDAwMDAzLTAwMDAtMDAwMC1jMDAwLTAwMDAwMDAwMDAwMAoKCgRzbmlkEgI2NBILCOi47e36zq0-EAUaCzIwLjIwLjMyLjk2KixqWlpqSUcxVEZWUTR1ODJZSUFWQ3luLzBXb3RxUmNWdlQ5VFdIbnorT1hJPTCZATgBQhChu60ugEAA0MYtH6GXHNtuShBoYXNoZWRwcm9vZnRva2VuUhJbImttc2kiLCJkdmNfY21wIl1qJDAwMjE0Yjg5LThiOWItZDk1ZC0xNWUxLTVhNjQwNGYyMGY2M3IpMGguZnxtZW1iZXJzaGlwfDEwMDMyMDAyOTg3Y2NkZWNAbGl2ZS5jb216ATKCARIJ0yWDHKLgPUkRuIKwimvZpx6SAQZNYXJjdXOaAQpOb3JkbGFuZGVyogEZbWFyY3VzLm5vcmRsYW5kZXJAc2J2dC5zZaoBEDEwMDMyMDAyOTg3Q0NERUOyAU1jb250YWluZXIuc2VsZWN0ZWQgYWxsZmlsZXMud3JpdGUgbXlmaWxlcy53cml0ZSBteWZpbGVzLnJlYWQgYWxscHJvZmlsZXMucmVhZMgBAQ.hOBesolCCMHAs4SBoTtQz-UrqZ-MuyXqIhODnXaB09A&ApiVersion=2.0&web=1)
SEWER_ALIASES = {
    "betong": {"betong", "concrete", "rörbetong", "rc", "btg"},
    "plast":  {"plast", "plastic", "peh", "pe", "pp", "pvc", "pvcn"},
    "ovrigt": {"övrigt", "ovrigt", "okänt", "unknown", "other", "misc", "diverse"}
}

def _match_alias(aliases: Dict[str, set], material: str) -> Optional[str]:
    m = _norm(material)
    for key, vocab in aliases.items():
        if m in (_norm(x) for x in vocab):
            return key
    # Fallback: substring heuristic
    for key, vocab in aliases.items():
        for token in vocab:
            if _norm(token) and _norm(token) in m:
                return key
    return None

def _as_mat(bucket: Dict, key: str) -> MaterialParams:
    if key not in bucket:
        raise KeyError(f"Material key '{key}' not found in parameters")
    rec = bucket[key]
    return MaterialParams(mu=float(rec["mu"]), sigma=float(rec["sigma"]))

def find_material_key(
    params: Dict,
    *,
    domain: str,                # 'water' or 'sewer'
    subtype: Optional[str],     # for sewer: 'spill' or 'storm'; ignored for water
    material_name: str,
    year: Optional[int]
) -> Tuple[str, MaterialParams]:
    dom = _norm(domain)
    if dom not in ("water", "sewer"):
        raise KeyError(f"domain must be 'water' or 'sewer', got: {domain}")

    if dom == "water":
        bucket = params.get("water")
        if not bucket:
            raise KeyError("parameters.json lacks 'water' section")
        base = _match_alias(WATER_ALIASES, material_name) or "ovrigt"
        if base in WATER_THRESHOLD and year is not None:
            for key, lo, hi in WATER_THRESHOLD[base]:
                if (lo is None or year >= lo) and (hi is None or year < hi):
                    return key, _as_mat(bucket, key)
        # If year missing or no split applies, map directly (PE, Övrigt, etc.)
        return (base if base != "ovrigt" else "ovrigt"), _as_mat(bucket, base if base != "ovrigt" else "ovrigt")

    # Sewer domain
    sec = _norm(subtype or "")
    if sec not in ("spill", "storm"):
        raise KeyError("For 'sewer', subtype must be 'spill' or 'storm'")

    sec_bucket = params.get("sewer", {}).get(sec)
    if not sec_bucket:
        raise KeyError(f"parameters.json lacks 'sewer.{sec}' section")

    base = _match_alias(SEWER_ALIASES, material_name) or "ovrigt"

    if base == "betong":
        if sec == "spill":
            # Spill Betong: <1950, 1950-1969, >=1970. [2](https://sbvt-my.sharepoint.com/personal/marcus_nordlander_sbvt_se/_layouts/15/download.aspx?UniqueId=3000430b-cc55-45b6-9ad1-fedb7dae09e2&Translate=false&tempauth=v1.eyJzaXRlaWQiOiJiMjEzNzkyNi1hOTQ5LTRjYzktYjZkNS03YzkxNTgxOGM3YTkiLCJhcHBfZGlzcGxheW5hbWUiOiJPZmZpY2UgMzY1IFNlYXJjaCBTZXJ2aWNlIiwiYXBwaWQiOiI2NmE4ODc1Ny0yNThjLTRjNzItODkzYy0zZThiZWQ0ZDY4OTkiLCJhdWQiOiIwMDAwMDAwMy0wMDAwLTBmZjEtY2UwMC0wMDAwMDAwMDAwMDAvc2J2dC1teS5zaGFyZXBvaW50LmNvbUAxYzgzMjVkMy1lMGEyLTQ5M2QtYjg4Mi1iMDhhNmJkOWE3MWUiLCJleHAiOiIxNzU1MTc5NzEyIn0.CkAKDGVudHJhX2NsYWltcxIwQ05LMjk4UUdFQUFhRm05bFNtTk1la1UzVmtWSFlXSnlkRjlOZGsxQ1FVRXFBQT09CjIKCmFjdG9yYXBwaWQSJDAwMDAwMDAzLTAwMDAtMDAwMC1jMDAwLTAwMDAwMDAwMDAwMAoKCgRzbmlkEgI2NBILCOi47e36zq0-EAUaCzIwLjIwLjMyLjk2KixqWlpqSUcxVEZWUTR1ODJZSUFWQ3luLzBXb3RxUmNWdlQ5VFdIbnorT1hJPTCZATgBQhChu60ugEAA0MYtH6GXHNtuShBoYXNoZWRwcm9vZnRva2VuUhJbImttc2kiLCJkdmNfY21wIl1qJDAwMjE0Yjg5LThiOWItZDk1ZC0xNWUxLTVhNjQwNGYyMGY2M3IpMGguZnxtZW1iZXJzaGlwfDEwMDMyMDAyOTg3Y2NkZWNAbGl2ZS5jb216ATKCARIJ0yWDHKLgPUkRuIKwimvZpx6SAQZNYXJjdXOaAQpOb3JkbGFuZGVyogEZbWFyY3VzLm5vcmRsYW5kZXJAc2J2dC5zZaoBEDEwMDMyMDAyOTg3Q0NERUOyAU1jb250YWluZXIuc2VsZWN0ZWQgYWxsZmlsZXMud3JpdGUgbXlmaWxlcy53cml0ZSBteWZpbGVzLnJlYWQgYWxscHJvZmlsZXMucmVhZMgBAQ.hOBesolCCMHAs4SBoTtQz-UrqZ-MuyXqIhODnXaB09A&ApiVersion=2.0&web=1)
            if year is None:
                key = "betong_1950_1969"      # neutral default if unknown
            elif year < 1950:
                key = "betong_<1950"
            elif year < 1970:
                key = "betong_1950_1969"
            else:
                key = "betong_>=1970"
        else:
            # Storm Betong: <1950, 1950-1969; if ≥1970, fall back to 1950-1969 (no explicit ≥1970 class). [2](https://sbvt-my.sharepoint.com/personal/marcus_nordlander_sbvt_se/_layouts/15/download.aspx?UniqueId=3000430b-cc55-45b6-9ad1-fedb7dae09e2&Translate=false&tempauth=v1.eyJzaXRlaWQiOiJiMjEzNzkyNi1hOTQ5LTRjYzktYjZkNS03YzkxNTgxOGM3YTkiLCJhcHBfZGlzcGxheW5hbWUiOiJPZmZpY2UgMzY1IFNlYXJjaCBTZXJ2aWNlIiwiYXBwaWQiOiI2NmE4ODc1Ny0yNThjLTRjNzItODkzYy0zZThiZWQ0ZDY4OTkiLCJhdWQiOiIwMDAwMDAwMy0wMDAwLTBmZjEtY2UwMC0wMDAwMDAwMDAwMDAvc2J2dC1teS5zaGFyZXBvaW50LmNvbUAxYzgzMjVkMy1lMGEyLTQ5M2QtYjg4Mi1iMDhhNmJkOWE3MWUiLCJleHAiOiIxNzU1MTc5NzEyIn0.CkAKDGVudHJhX2NsYWltcxIwQ05LMjk4UUdFQUFhRm05bFNtTk1la1UzVmtWSFlXSnlkRjlOZGsxQ1FVRXFBQT09CjIKCmFjdG9yYXBwaWQSJDAwMDAwMDAzLTAwMDAtMDAwMC1jMDAwLTAwMDAwMDAwMDAwMAoKCgRzbmlkEgI2NBILCOi47e36zq0-EAUaCzIwLjIwLjMyLjk2KixqWlpqSUcxVEZWUTR1ODJZSUFWQ3luLzBXb3RxUmNWdlQ5VFdIbnorT1hJPTCZATgBQhChu60ugEAA0MYtH6GXHNtuShBoYXNoZWRwcm9vZnRva2VuUhJbImttc2kiLCJkdmNfY21wIl1qJDAwMjE0Yjg5LThiOWItZDk1ZC0xNWUxLTVhNjQwNGYyMGY2M3IpMGguZnxtZW1iZXJzaGlwfDEwMDMyMDAyOTg3Y2NkZWNAbGl2ZS5jb216ATKCARIJ0yWDHKLgPUkRuIKwimvZpx6SAQZNYXJjdXOaAQpOb3JkbGFuZGVyogEZbWFyY3VzLm5vcmRsYW5kZXJAc2J2dC5zZaoBEDEwMDMyMDAyOTg3Q0NERUOyAU1jb250YWluZXIuc2VsZWN0ZWQgYWxsZmlsZXMud3JpdGUgbXlmaWxlcy53cml0ZSBteWZpbGVzLnJlYWQgYWxscHJvZmlsZXMucmVhZMgBAQ.hOBesolCCMHAs4SBoTtQz-UrqZ-MuyXqIhODnXaB09A&ApiVersion=2.0&web=1)
            if year is None or year >= 1950:
                key = "betong_1950_1969"
            else:
                key = "betong_<1950"
    else:
        key = base  # plast / ovrigt

    return key, _as_mat(sec_bucket, key)
