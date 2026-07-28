"""Deterministic cross-question attitude profiles for synthetic respondents."""
import hashlib

PROFILE_VERSION = "attitude-profile-v1"


def _unit(uuid, salt):
    raw = f"{uuid}|{salt}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16) / 0xFFFFFFFF


def build_attitude_profile(persona, demographics=None):
    """Return a stable latent profile reused across survey phases."""
    p = persona or {}
    d = demographics or {}
    edu = int(d.get("Q3", 2) or 2)
    age = int(p.get("age", d.get("Q2", 40)) or 40)
    edu_mod = {1: -0.10, 2: 0.0, 3: 0.10}.get(edu, 0.0)
    age_mod = 0.05 if 40 <= age <= 59 else (-0.03 if age < 30 else 0.0)
    uid = p.get("uuid", "")
    return {
        "version": PROFILE_VERSION,
        "risk_sensitivity": min(1.0, max(0.0, 0.18 + 0.58 * _unit(uid, "risk") + 0.08 * age_mod)),
        "technology_trust": min(1.0, max(0.0, 0.20 + 0.50 * _unit(uid, "tech") + edu_mod)),
        "institutional_trust": 0.18 + 0.64 * _unit(uid, "trust"),
        "local_attachment": 0.16 + 0.68 * _unit(uid, "local"),
        "uncertainty": min(1.0, max(0.0, 0.12 + 0.58 * _unit(uid, "uncertainty") - 0.08 * edu_mod)),
    }


def _level(value):
    return "낮은 편" if value < 0.34 else "보통 수준" if value < 0.67 else "높은 편"


def render_attitude_profile(profile):
    return "\n".join([
        f"- 재난 위험 민감도: {_level(profile['risk_sensitivity'])}",
        f"- 과학기술 신뢰·수용 성향: {_level(profile['technology_trust'])}",
        f"- 정부·공공기관 신뢰 성향: {_level(profile['institutional_trust'])}",
        f"- 거주지 애착: {_level(profile['local_attachment'])}",
        f"- 정보 부족·판단 유보 성향: {_level(profile['uncertainty'])}",
        "- 문항마다 완전히 다른 사람이 되지 말고, 이 성향과 개인 배경이 문항 간에 일관되게 드러나도록 답하십시오.",
    ])
