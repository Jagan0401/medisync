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
from pymongo import UpdateOne

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

    # Mark pipeline as running
    db.pipeline_state.update_one(
        {'_id': 'current'},
        {'$set': {'status': 'running', 'stage': 'Loading patients', 'started_at': now.isoformat(), 'progress': 0}},
        upsert=True,
    )

    patients = list(db.patients.find({}, {'_id': 1, 'patient_id': 1, 'name': 1, 'disease': 1,
                                           'last_result': 1, 'age': 1, 'overdue_days': 1,
                                           'phone': 1, 'hospital': 1, 'channel': 1}))
    total = len(patients)
    logger.info('Loaded %d patients from MongoDB', total)

    # Update stage
    db.pipeline_state.update_one({'_id': 'current'}, {'$set': {
        'stage': 'Risk scoring', 'progress': 10, 'total_patients': total,
    }})

    stats = {'total': total, 'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0, 'gaps_found': 0}
    ai_decisions = []
    care_gaps = []
    critical_queue = []
    high_queue = []
    medium_queue = []
    low_queue = []

    risk_updates = []
    for i, p in enumerate(patients):
        # ── Step 1: Risk Engine ──
        risk = calculate_risk(p)
        score = calculate_risk_score(p)
        stats[risk] += 1

        risk_updates.append(UpdateOne(
            {'_id': p['_id']},
            {'$set': {'risk': risk, 'risk_score': score, 'risk_updated_at': now.isoformat()}},
        ))

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
        p_dict = {k: v for k, v in p.items() if k != '_id'}
        phone = p_dict.get('phone', '')
        if phone and gap:
            entry = {**p_dict, 'risk': risk, 'risk_score': score}
            if risk == 'Critical':
                critical_queue.append(entry)
            elif risk == 'High':
                high_queue.append(entry)
            elif risk == 'Medium':
                medium_queue.append(entry)
            else:
                low_queue.append(entry)

    # ── Bulk-write risk updates ──
    db.pipeline_state.update_one({'_id': 'current'}, {'$set': {
        'stage': 'Saving risk scores', 'progress': 50,
    }})
    batch_size = 1000
    for i in range(0, len(risk_updates), batch_size):
        db.patients.bulk_write(risk_updates[i:i + batch_size], ordered=False)

    # ── Step 5: Store results in MongoDB ──
    db.pipeline_state.update_one({'_id': 'current'}, {'$set': {
        'stage': 'Storing AI decisions', 'progress': 70,
    }})

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

    # ── Add activity feed entries ──
    feed_time = now.strftime('%Y-%m-%d %H:%M')
    feed_entries = [
        {
            'scope': 'superadmin',
            'icon': '🔬',
            'text': f"Pipeline analyzed {stats['total']:,} patients — Critical:{stats['Critical']:,} High:{stats['High']:,} Medium:{stats['Medium']:,} Low:{stats['Low']:,}",
            'time': feed_time,
            'created_at': now,
        },
        {
            'scope': 'superadmin',
            'icon': '⚠️',
            'text': f"{stats['gaps_found']:,} care gaps detected across all hospitals",
            'time': feed_time,
            'created_at': now,
        },
    ]
    msg_queue_total = len(critical_queue) + len(high_queue) + len(medium_queue) + len(low_queue)
    if msg_queue_total:
        feed_entries.append({
            'scope': 'superadmin',
            'icon': '🤖',
            'text': f"AI queued {msg_queue_total:,} WhatsApp outreach messages",
            'time': feed_time,
            'created_at': now,
        })

    # Hospital-admin scoped feed entries
    feed_entries.append({
        'scope': 'hospital_admin',
        'icon': '🔬',
        'text': f"AI engine processed {stats['total']:,} patients — {stats['gaps_found']:,} care gaps detected",
        'time': feed_time,
        'created_at': now,
    })
    feed_entries.append({
        'scope': 'hospital_admin',
        'icon': '📊',
        'text': f"Risk distribution: Critical {stats['Critical']:,} | High {stats['High']:,} | Medium {stats['Medium']:,} | Low {stats['Low']:,}",
        'time': feed_time,
        'created_at': now,
    })
    if msg_queue_total:
        feed_entries.append({
            'scope': 'hospital_admin',
            'icon': '💬',
            'text': f"{msg_queue_total:,} patient outreach messages queued for delivery",
            'time': feed_time,
            'created_at': now,
        })

    # Doctor-scoped feed entries
    feed_entries.append({
        'scope': 'doctor',
        'icon': '📋',
        'text': f"AI analyzed {stats['total']:,} patients — {stats['Critical']:,} critical, {stats['High']:,} high-risk flagged",
        'time': feed_time,
        'created_at': now,
    })
    feed_entries.append({
        'scope': 'doctor',
        'icon': '⚠️',
        'text': f"{stats['gaps_found']:,} care gaps detected — review overdue tests",
        'time': feed_time,
        'created_at': now,
    })

    db.activity_feed.insert_many(feed_entries)

    # Log the pipeline run
    db.audit_logs.insert_one({
        'scope': 'superadmin',
        'user': 'SYSTEM',
        'action': f"Daily pipeline: {stats['total']} patients analyzed — "
                  f"Critical:{stats['Critical']} High:{stats['High']} "
                  f"Medium:{stats['Medium']} Low:{stats['Low']} "
                  f"Gaps:{stats['gaps_found']}",
        'hospital': 'ALL',
        'time': feed_time,
    })

    # ── Step 6: Dispatch messages tier-by-tier ──
    db.pipeline_state.update_one({'_id': 'current'}, {'$set': {
        'stage': 'Dispatching messages', 'progress': 85,
    }})

    messages_dispatched = 0
    try:
        from tasks.message_dispatcher import dispatch_messages_batch
        if critical_queue:
            dispatch_messages_batch.delay([_serialise(p) for p in critical_queue], 'Critical')
            messages_dispatched += len(critical_queue)
        if high_queue:
            dispatch_messages_batch.delay([_serialise(p) for p in high_queue], 'High')
            messages_dispatched += len(high_queue)
        if medium_queue:
            dispatch_messages_batch.delay([_serialise(p) for p in medium_queue], 'Medium')
            messages_dispatched += len(medium_queue)
        if low_queue:
            dispatch_messages_batch.delay([_serialise(p) for p in low_queue], 'Low')
            messages_dispatched += len(low_queue)
    except Exception as exc:
        logger.warning('Message dispatch skipped (Celery/Redis unavailable): %s', exc)

    # Mark pipeline complete
    stats['messages_queued'] = msg_queue_total
    stats['messages_dispatched'] = messages_dispatched
    db.pipeline_state.update_one({'_id': 'current'}, {'$set': {
        'status': 'completed',
        'stage': 'Complete',
        'progress': 100,
        'completed_at': datetime.utcnow().isoformat(),
        'stats': stats,
    }})

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
