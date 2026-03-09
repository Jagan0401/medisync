"""
Risk Engine — Scores each patient from the MongoDB patients collection.

Risk tiers:
  Critical  — last_result >= 10 OR (age > 65 AND last_result >= 8)
  High      — last_result >= 8 OR (age > 60 AND last_result >= 7)
  Medium    — last_result >= 6.5 OR age > 55
  Low       — everything else
"""


def calculate_risk(patient):
    """Return one of: Critical, High, Medium, Low."""
    result = patient.get('last_result', 0)
    age = patient.get('age', 0)
    disease = patient.get('disease', '')

    # Try to parse result if it's a string like "9.5%"
    if isinstance(result, str):
        try:
            result = float(result.replace('%', '').strip())
        except (ValueError, AttributeError):
            result = 0

    if isinstance(age, str):
        try:
            age = int(age)
        except (ValueError, AttributeError):
            age = 0

    # ── Scoring ──
    if result >= 10 or (age > 65 and result >= 8):
        return 'Critical'

    if result >= 8 or (age > 60 and result >= 7):
        return 'High'

    if result >= 6.5 or age > 55:
        return 'Medium'

    return 'Low'


def calculate_risk_score(patient):
    """Return a numeric score 0-100 for sorting priority."""
    result = patient.get('last_result', 0)
    age = patient.get('age', 0)

    if isinstance(result, str):
        try:
            result = float(result.replace('%', '').strip())
        except (ValueError, AttributeError):
            result = 0

    if isinstance(age, str):
        try:
            age = int(age)
        except (ValueError, AttributeError):
            age = 0

    score = min(result * 8, 60) + min(age * 0.5, 30)
    overdue = patient.get('overdue_days', 0) or 0
    score += min(overdue * 0.2, 10)
    return round(min(score, 100), 1)
