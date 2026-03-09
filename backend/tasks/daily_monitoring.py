"""
Daily Monitoring — Celery tasks that run the full pipeline:

  1. Scan all patients from MongoDB
  2. Run risk engine → compute/update risk tier for every patient
  3. Run care gap engine → detect overdue tests
  4. Store AI decisions and updated risk scores
  5. Kick off message dispatcher for each tier (Critical → High → Medium → Low)
"""

import logging
from datetime import datetime

from celery import shared_task
from config.db import db
from services.risk_engine import calculate_risk, calculate_risk_score
from services.care_gap_engine import detect_care_gap

logger = logging.getLogger(__name__)


@shared_task(name='tasks.run_daily_pipeline')
def run_daily_pipeline():
    """
    Main daily pipeline — scheduled via Celery Beat.
    Analyzes ALL patients, updates risk, detects gaps, queues messages.
    """
    logger.info('═══ Daily Pipeline START ═══')
    now = datetime.utcnow()

    patients = list(db.patients.find({}, {'_id': 0}))
    logger.info('Loaded %d patients from MongoDB', len(patients))

    stats = {'total': len(patients), 'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0, 'gaps_found': 0}
    ai_decisions = []
    care_gaps = []
    critical_queue = []
    high_queue = []
    medium_queue = []
    low_queue = []

    for p in patients:
        # ── Step 1: Risk Engine ──
        risk = calculate_risk(p)
        score = calculate_risk_score(p)
        stats[risk] += 1

        # Update patient record with computed risk
        db.patients.update_one(
            {'patient_id': p.get('patient_id')},
            {'$set': {'risk': risk, 'risk_score': score, 'risk_updated_at': now.isoformat()}},
        )

        # ── Step 2: Care Gap Engine ──
        gap = detect_care_gap(p)
        if gap:
            gap['risk'] = risk
            care_gaps.append(gap)
            stats['gaps_found'] += 1

        # ── Step 3: AI Reasoning — record decision ──
        action = _decide_action(risk, gap)
        ai_decisions.append({
            'patient': p.get('name', p.get('patient_id', '')),
            'patient_id': p.get('patient_id', ''),
            'hospital': p.get('hospital', ''),
            'risk': risk,
            'score': score,
            'action': action,
            'decided_at': now.isoformat(),
        })

        # ── Step 4: Queue for messaging ──
        phone = p.get('phone', '')
        if phone and gap:
            entry = {**p, 'risk': risk, 'risk_score': score}
            if risk == 'Critical':
                critical_queue.append(entry)
            elif risk == 'High':
                high_queue.append(entry)
            elif risk == 'Medium':
                medium_queue.append(entry)
            else:
                low_queue.append(entry)

    # ── Step 5: Store results in MongoDB ──
    if ai_decisions:
        db.ai_decisions.delete_many({})
        db.ai_decisions.insert_many(ai_decisions)

    if care_gaps:
        db.care_gaps.delete_many({})
        db.care_gaps.insert_many(care_gaps)

    # Update analytics
    db.analytics.update_one(
        {'scope': 'superadmin', 'label': 'Risk — Critical'},
        {'$set': {'value': str(stats['Critical'])}},
        upsert=True,
    )
    db.analytics.update_one(
        {'scope': 'superadmin', 'label': 'Risk — High'},
        {'$set': {'value': str(stats['High'])}},
        upsert=True,
    )
    db.analytics.update_one(
        {'scope': 'superadmin', 'label': 'Care Gaps Open'},
        {'$set': {'value': str(stats['gaps_found'])}},
        upsert=True,
    )

    # Log the pipeline run
    db.audit_logs.insert_one({
        'scope': 'superadmin',
        'user': 'SYSTEM',
        'action': f"Daily pipeline: {stats['total']} patients analyzed — "
                  f"Critical:{stats['Critical']} High:{stats['High']} "
                  f"Medium:{stats['Medium']} Low:{stats['Low']} "
                  f"Gaps:{stats['gaps_found']}",
        'hospital': 'ALL',
        'time': now.strftime('%Y-%m-%d %H:%M'),
    })

    # ── Step 6: Dispatch messages tier-by-tier ──
    from tasks.message_dispatcher import dispatch_messages_batch
    if critical_queue:
        dispatch_messages_batch.delay([_serialise(p) for p in critical_queue], 'Critical')
    if high_queue:
        dispatch_messages_batch.delay([_serialise(p) for p in high_queue], 'High')
    if medium_queue:
        dispatch_messages_batch.delay([_serialise(p) for p in medium_queue], 'Medium')
    if low_queue:
        dispatch_messages_batch.delay([_serialise(p) for p in low_queue], 'Low')

    logger.info('═══ Daily Pipeline END ═══  stats=%s', stats)
    return stats


def _decide_action(risk, gap):
    """Return a human-readable AI decision string."""
    if not gap:
        return 'No action — tests up-to-date'
    if risk == 'Critical':
        return 'Immediate WhatsApp outreach + Home collection offer'
    if risk == 'High':
        return 'WhatsApp reminder — urgent follow-up needed'
    if risk == 'Medium':
        return 'WhatsApp reminder — routine check overdue'
    return 'WhatsApp reminder — gentle nudge for test'


def _serialise(patient):
    """Strip ObjectId so it can be JSON-serialised by Celery."""
    return {k: v for k, v in patient.items() if k != '_id'}
