"""
Care Gap Engine — Detects patients with overdue / missing tests
and generates care_gap documents in MongoDB.
"""

from datetime import datetime


# Test frequency rules (days between tests)
PROTOCOL_MAP = {
    'Diabetes': {'test': 'HbA1c', 'frequency_days': 90},
    'Hypertension': {'test': 'BP Panel', 'frequency_days': 60},
    'Thyroid': {'test': 'T3/T4/TSH', 'frequency_days': 180},
    'Kidney Disease': {'test': 'Creatinine', 'frequency_days': 90},
    'Cardiac': {'test': 'Lipid Profile', 'frequency_days': 120},
    'Anemia': {'test': 'CBC', 'frequency_days': 90},
}


def detect_care_gap(patient):
    """
    Returns a care_gap dict if the patient is overdue, else None.
    """
    disease = patient.get('disease', '')
    protocol = PROTOCOL_MAP.get(disease)
    if not protocol:
        # Default fallback 90-day rule
        protocol = {'test': patient.get('last_test', 'General Checkup'), 'frequency_days': 90}

    overdue_days = patient.get('overdue_days', 0) or 0
    if overdue_days <= 0:
        return None

    return {
        'patient_id': patient.get('patient_id', ''),
        'patient_name': patient.get('name', ''),
        'hospital': patient.get('hospital', ''),
        'disease': disease,
        'test_required': protocol['test'],
        'frequency_days': protocol['frequency_days'],
        'overdue_days': overdue_days,
        'status': 'Open',
        'risk': patient.get('risk', 'Low'),
        'detected_at': datetime.utcnow().isoformat(),
    }


def detect_gaps_batch(patients):
    """Process a list of patients, return list of care_gap dicts."""
    gaps = []
    for p in patients:
        gap = detect_care_gap(p)
        if gap:
            gaps.append(gap)
    return gaps
