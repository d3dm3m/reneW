# calculation_logic.py
# Normal-distribution cohort renewal model for VA-ledningar
#
# renewal_km = L * [Phi((age1−μ)/σ) − Phi((age0−μ)/σ)]
# Guardrails: clamp CDF to [0,1], treat negative ages as F=0 at that bound.

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Tuple, Dict
import math

# Optional: use SciPy if available
try:
    from scipy.stats import norm as _scipy_norm  # type: ignore
except Exception:  # pragma: no cover
    _scipy_norm = None

SQRT2 = math.sqrt(2.0)
Z_0P9 = 1.2815515655446004  # Phi^{-1}(0.9) – used only by derive_sigma_from_t50_t90

def normal_cdf(x: float, mu: float, sigma: float) -> float:
    """Return Phi((x - mu)/sigma). Uses SciPy if available; otherwise math.erf."""
    if sigma <= 0:
        sigma = 1e-9
    z = (x - mu) / sigma
    if _scipy_norm is not None:
        return float(_scipy_norm.cdf(z))
    return 0.5 * (1.0 + math.erf(z / SQRT2))

def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

@dataclass(frozen=True)
class MaterialParams:
    mu: float
    sigma: float

@dataclass(frozen=True)
class Cohort:
    length_km: float
    install_year: int
    material_key: str  # not required for math; useful for debugging

def renewal_for_cohort_period(
    cohort: Cohort,
    t0: int,
    t1: int,
    params: MaterialParams,
) -> float:
    """Compute renewal (km) for a cohort in [t0, t1)."""
    if t1 <= t0:
        return 0.0

    age0 = t0 - cohort.install_year
    age1 = t1 - cohort.install_year

    F0 = 0.0 if age0 <= 0 else clamp01(normal_cdf(age0, params.mu, params.sigma))
    F1 = 0.0 if age1 <= 0 else clamp01(normal_cdf(age1, params.mu, params.sigma))

    dF = F1 - F0
    if dF <= 0:
        return 0.0
    return min(cohort.length_km, cohort.length_km * dF)

def renewal_totals(
    cohorts: Iterable[Cohort],
    periods: Iterable[Tuple[int, int]],
    materials: Dict[str, MaterialParams],
) -> List[float]:
    """Return total renewals (km) per period across all cohorts."""
    totals: List[float] = []
    for (t0, t1) in periods:
        s = 0.0
        for c in cohorts:
            mp = materials[c.material_key]
            s += renewal_for_cohort_period(c, t0, t1, mp)
        totals.append(s)
    return totals

def cumulative_by_period(values: Iterable[float]) -> List[float]:
    out: List[float] = []
    acc = 0.0
    for v in values:
        acc += v
        out.append(acc)
    return out

def derive_sigma_from_t50_t90(t50: float, t90: float) -> float:
    """For a normal model: mu ≈ t50; sigma ≈ (t90 - t50) / z_{0.9}."""
    if t90 <= t50:
        return 0.0
    return (t90 - t50) / Z_0P9

def decades_from(start: int, n_periods: int) -> List[Tuple[int, int]]:
    return [(start + 10*i, start + 10*(i+1)) for i in range(n_periods)]

def cumulative_failure_probability(cohort, year, params):
    """
    Returns the cumulative probability of failure (F(t))
    for a given cohort up to the given year.
    """
    import math
    t = max(0, year - cohort.install_year)
    mu = params.mu
    sigma = params.sigma
    # Standard normal CDF
    z = (t - mu) / sigma
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))

if __name__ == "__main__":
    # Quick smoke test
    pe = MaterialParams(mu=125.6, sigma=27.7)
    cohorts = [Cohort(length_km=10.0, install_year=2000, material_key="pe")]
    periods = decades_from(2020, 3)
    totals = renewal_totals(cohorts, periods, {"pe": pe})
    print("Per-decade renewals:", totals)
