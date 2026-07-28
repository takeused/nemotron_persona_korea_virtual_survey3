"""Optional latent-engagement adjustment for post-stratification."""
import hashlib

ENGAGEMENT_VERSION = "engagement-weight-v1"
DEFAULT_TARGET = {"low": 0.25, "mid": 0.50, "high": 0.25}


def engagement_score(persona, demographics=None):
    """Score engagement without using Q5, avoiding circular outcome weighting."""
    p = persona or {}
    d = demographics or {}
    edu = int(d.get("Q3", 2) or 2)
    age = int(p.get("age", d.get("Q2", 40)) or 40)
    edu_component = {1: 0.20, 2: 0.50, 3: 0.80}.get(edu, 0.50)
    age_component = 0.58 if 30 <= age <= 59 else 0.45
    seed = int(hashlib.sha256(str(p.get("uuid", "")).encode()).hexdigest()[:8], 16)
    latent_component = seed / 0xFFFFFFFF
    return min(1.0, max(0.0, 0.45 * latent_component + 0.35 * edu_component + 0.20 * age_component))


def engagement_band(score):
    return "low" if score < 1 / 3 else "mid" if score < 2 / 3 else "high"


def engagement_factors(records, target=None):
    """Normalize low/mid/high engagement composition to the configured target."""
    target = target or DEFAULT_TARGET
    if not records:
        return []
    bands = [engagement_band(float(r.get("engagement_score", 0.5))) for r in records]
    counts = {b: bands.count(b) for b in ("low", "mid", "high")}
    n = len(records)
    factors = []
    for band in bands:
        share = counts[band] / n
        factors.append(target.get(band, share) / share if share else 1.0)
    mean = sum(factors) / n or 1.0
    return [f / mean for f in factors]
