"""
Risk Engine — Scores each patient from the MongoDB patients collection.

Disease-specific thresholds:
  Diabetes (HbA1c %):     Critical >=10, High >=8, Medium >=6.5
  Hypertension (systolic): Critical >=180, High >=160, Medium >=140
  CKD (Creatinine mg/dL):  Critical >=4, High >=2.5, Medium >=1.5
  Hypothyroidism (TSH):    Critical >=10, High >=7, Medium >=5
"""

# Per-disease thresholds: (critical, high, medium)
_THRESHOLDS = {
    'Diabetes':       (10, 8, 6.5),
    'Hypertension':   (180, 160, 140),
    'CKD':            (4, 2.5, 1.5),
    'Hypothyroidism': (10, 7, 5),
    'Kidney Disease': (4, 2.5, 1.5),
    'Cardiac':        (240, 200, 170),
    'Anemia':         (7, 9, 11),       # Hb — lower is worse, handled below
}

# Diseases where LOWER result = HIGHER risk
_LOWER_IS_WORSE = {'Anemia'}


def _parse_number(val):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace('%', '').strip().split('/')[0])
        except (ValueError, AttributeError):
            return 0
    return 0


def calculate_risk(patient):
    """Return one of: Critical, High, Medium, Low."""
    result = _parse_number(patient.get('last_result', 0))
    age = _parse_number(patient.get('age', 0))
    disease = patient.get('disease', '')

    thresholds = _THRESHOLDS.get(disease, (10, 8, 6.5))
    crit, high, med = thresholds

    if disease in _LOWER_IS_WORSE:
        # Lower values are worse (e.g. Anemia Hb)
        if result <= crit or (age > 65 and result <= high):
            return 'Critical'
        if result <= high or (age > 60 and result <= med):
            return 'High'
        if result <= med or age > 55:
            return 'Medium'
        return 'Low'

    # Normal: higher values are worse
    if result >= crit or (age > 65 and result >= high):
        return 'Critical'
    if result >= high or (age > 60 and result >= med):
        return 'High'
    if result >= med or age > 55:
        return 'Medium'
    return 'Low'


def calculate_risk_score(patient):
    """Return a numeric score 0-100 for sorting priority."""
    result = _parse_number(patient.get('last_result', 0))
    age = _parse_number(patient.get('age', 0))
    disease = patient.get('disease', '')

    thresholds = _THRESHOLDS.get(disease, (10, 8, 6.5))
    crit_val = thresholds[0]

    # Normalise result to a 0-60 range relative to the critical threshold
    if disease in _LOWER_IS_WORSE:
        ratio = max(0, (crit_val - result) / max(crit_val, 1)) if crit_val else 0
    else:
        ratio = min(result / max(crit_val, 1), 1.5)
    score = ratio * 40

    score += min(age * 0.4, 25)

    overdue = patient.get('overdue_days', 0) or 0
    score += min(overdue * 0.15, 15)

    risk = calculate_risk(patient)
    tier_bonus = {'Critical': 20, 'High': 12, 'Medium': 5, 'Low': 0}
    score += tier_bonus.get(risk, 0)

    return round(min(score, 100), 1)
