"""
REST API endpoints that serve dashboard data from MongoDB.
Each role gets a single GET endpoint returning everything its Flutter screen needs.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.db import db


def _mongo_list(collection, query=None, limit=0, sort=None):
    cursor = collection.find(query or {}, {'_id': 0})
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def _mongo_count(collection, query=None):
    return collection.count_documents(query or {})


# ─── DOCTOR ────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_dashboard_api(request):
    patients_raw = _mongo_list(db.patients, sort=[('overdue_days', -1)], limit=50)
    patients = [
        {
            'id': p.get('patient_id', ''),
            'name': p.get('name', ''),
            'condition': p.get('disease', ''),
            'lastTest': p.get('last_test', ''),
            'risk': _map_risk(p.get('risk', 'Low')),
        }
        for p in patients_raw
    ]

    care_gaps_raw = _mongo_list(db.care_gaps, sort=[('overdue_days', -1)], limit=50)
    care_gaps = [
        {
            'patientName': g.get('patient', g.get('patient_name', '')),
            'testOverdue': g.get('test', g.get('test_overdue', '')),
            'delay': g.get('overdue_days', g.get('delay', '')),
            'risk': _map_risk(g.get('risk', 'Low')),
            'escalated': g.get('escalated', False),
        }
        for g in care_gaps_raw
    ]

    test_results_raw = _mongo_list(db.test_results, limit=50)
    lab_results = [
        {
            'patientName': t.get('patient', t.get('patient_name', '')),
            'testName': t.get('test', t.get('test_name', '')),
            'result': t.get('result', t.get('value', '')),
            'date': t.get('date', ''),
        }
        for t in test_results_raw
    ]

    appointments_raw = _mongo_list(db.appointments)
    appointments = [
        {
            'patientName': a.get('patient', a.get('patient_name', '')),
            'purpose': a.get('purpose', ''),
            'date': a.get('date', ''),
            'status': a.get('status', 'Scheduled'),
        }
        for a in appointments_raw
    ]

    feed = _mongo_list(db.activity_feed, {'scope': 'doctor'})
    activity_feed = [
        {'icon': f.get('icon', '📋'), 'text': f.get('text', ''), 'time': f.get('time', '')}
        for f in feed
    ]

    audit_raw = _mongo_list(db.audit_logs, {'scope': 'doctor'})
    audit_log = [
        {'icon': a.get('icon', '🔒'), 'text': a.get('text', a.get('action', '')), 'time': a.get('time', a.get('timestamp', ''))}
        for a in audit_raw
    ]

    total_patients = _mongo_count(db.patients)
    critical_alerts = _mongo_count(db.patients, {'risk': {'$in': ['High', 'Critical']}})
    open_gaps = _mongo_count(db.care_gaps, {'status': 'Open'})
    closed_gaps = _mongo_count(db.care_gaps, {'status': 'Closed'})

    risk_low = _mongo_count(db.patients, {'risk': 'Low'})
    risk_med = _mongo_count(db.patients, {'risk': 'Medium'})
    risk_high = _mongo_count(db.patients, {'risk': 'High'})
    risk_crit = _mongo_count(db.patients, {'risk': 'Critical'})

    user = request.user
    doctor_name = user.get_full_name() or user.username

    return Response({
        'patients': patients,
        'care_gaps': care_gaps,
        'lab_results': lab_results,
        'appointments': appointments,
        'activity_feed': activity_feed,
        'audit_log': audit_log,
        'metrics': {
            'total_patients': total_patients,
            'critical_alerts': critical_alerts,
            'care_gaps_open': open_gaps,
            'care_gaps_closed': closed_gaps,
        },
        'caseload': [
            {'label': 'Low', 'fraction': risk_low / max(total_patients, 1), 'isCritical': False},
            {'label': 'Medium', 'fraction': risk_med / max(total_patients, 1), 'isCritical': False},
            {'label': 'High', 'fraction': risk_high / max(total_patients, 1), 'isCritical': True},
            {'label': 'Critical', 'fraction': risk_crit / max(total_patients, 1), 'isCritical': True},
        ],
        'doctor_name': doctor_name,
    })


# ─── HOSPITAL ADMIN ─────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hospital_admin_dashboard_api(request):
    patients_raw = _mongo_list(db.patients, sort=[('overdue_days', -1)], limit=50)
    patients = [
        {
            'id': p.get('patient_id', ''),
            'name': p.get('name', ''),
            'disease': p.get('disease', ''),
            'lastTest': p.get('last_test', ''),
            'risk': p.get('risk', 'Low'),
            'status': p.get('care_gap', 'Open'),
        }
        for p in patients_raw
    ]

    doctors = _mongo_list(db.doctors)
    doctors_out = [
        {'name': d.get('name', ''), 'specialty': d.get('specialty', ''), 'patients': d.get('patients', 0)}
        for d in doctors
    ]

    technicians = _mongo_list(db.technicians)
    techs_out = [
        {'name': t.get('name', ''), 'area': t.get('area', t.get('specialty', ''))}
        for t in technicians
    ]

    care_gaps_raw = _mongo_list(db.care_gaps, sort=[('overdue_days', -1)], limit=50)
    care_gaps = [
        {
            'patient': g.get('patient', ''),
            'test': g.get('test', ''),
            'delay': str(g.get('overdue_days', g.get('delay', ''))),
            'risk': g.get('risk', 'Low'),
        }
        for g in care_gaps_raw
    ]

    bookings_raw = _mongo_list(db.bookings)
    bookings = [
        {
            'patient': b.get('patient', ''),
            'test': b.get('test', ''),
            'technician': b.get('technician', ''),
            'date': b.get('date', ''),
            'status': b.get('status', 'Scheduled'),
        }
        for b in bookings_raw
    ]

    messages_raw = _mongo_list(db.messages)
    messages = [
        {
            'patient': m.get('patient', ''),
            'channel': m.get('channel', 'WhatsApp'),
            'message': m.get('message', ''),
            'status': m.get('status', 'Sent'),
        }
        for m in messages_raw
    ]

    feed = [
        {'icon': f.get('icon', '📋'), 'text': f.get('text', ''), 'time': f.get('time', '')}
        for f in _mongo_list(db.activity_feed, {'scope': 'hospital_admin'})
    ]

    audit = [
        {'actor': a.get('actor', a.get('user', '')), 'action': a.get('action', ''), 'time': a.get('time', a.get('timestamp', ''))}
        for a in _mongo_list(db.audit_logs, {'scope': 'hospital_admin'})
    ]

    protocols = _mongo_list(db.protocols)
    protocols_out = [
        {'name': p.get('name', ''), 'status': p.get('status', '')}
        for p in protocols
    ]

    total_patients = _mongo_count(db.patients)
    open_gaps = _mongo_count(db.care_gaps, {'status': 'Open'})
    closed_gaps = _mongo_count(db.care_gaps, {'status': 'Closed'})
    booking_count = _mongo_count(db.bookings)

    # Disease distribution
    disease_data = []
    for d in db.patients.aggregate([
        {'$group': {'_id': '$disease', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 6},
    ]):
        pct = round(d['count'] / max(total_patients, 1) * 100)
        disease_data.append({'label': d['_id'] or 'Unknown', 'pct': pct})

    user = request.user
    hospital_name = ''
    org = getattr(user, 'organization', None)
    if org:
        hospital_name = org.name
    if not hospital_name:
        h = db.hospitals.find_one({}, {'name': 1, '_id': 0})
        hospital_name = h.get('name', 'Hospital') if h else 'Hospital'

    return Response({
        'patients': patients,
        'doctors': doctors_out,
        'technicians': techs_out,
        'care_gaps': care_gaps,
        'bookings': bookings,
        'messages': messages,
        'activity_feed': feed,
        'audit_log': audit,
        'protocols': protocols_out,
        'disease_data': disease_data,
        'metrics': {
            'total_patients': total_patients,
            'care_gaps_open': open_gaps,
            'care_gaps_closed': closed_gaps,
            'bookings': booking_count,
        },
        'admin_name': user.get_full_name() or user.username,
        'hospital_name': hospital_name,
    })


# ─── LAB TECHNICIAN ─────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def technician_dashboard_api(request):
    bookings_raw = _mongo_list(db.bookings)
    patients_map = {}
    for p in db.patients.find({}, {'_id': 0, 'name': 1, 'disease': 1, 'age': 1,
                                    'phone': 1, 'patient_id': 1, 'hospital': 1, 'doctor': 1}):
        patients_map[p.get('name', '')] = p

    tasks = []
    for b in bookings_raw:
        pinfo = patients_map.get(b.get('patient', ''), {})
        tasks.append({
            'patientName': b.get('patient', ''),
            'testName': b.get('test', ''),
            'address': pinfo.get('hospital', b.get('hospital', '')),
            'timeSlot': b.get('date', ''),
            'patientId': pinfo.get('patient_id', ''),
            'age': str(pinfo.get('age', '')),
            'assignedDoctor': pinfo.get('doctor', ''),
            'condition': pinfo.get('disease', ''),
            'status': _map_collection_status(b.get('status', 'Scheduled')),
        })

    samples_raw = _mongo_list(db.test_results)
    samples = [
        {
            'sampleId': s.get('sample_id', s.get('test_id', f"S-{i+1001}")),
            'patientName': s.get('patient', ''),
            'testName': s.get('test', ''),
            'collectedAt': s.get('date', s.get('collected_at', '')),
            'status': _map_sample_status(s.get('status', 'pending')),
        }
        for i, s in enumerate(samples_raw)
    ]

    route_stops = [
        {
            'timeSlot': b.get('date', ''),
            'patientName': b.get('patient', ''),
            'location': patients_map.get(b.get('patient', ''), {}).get('hospital', ''),
            'confirmed': b.get('status', '') != 'Cancelled',
        }
        for b in bookings_raw
    ]

    comm_logs = [
        {
            'patientName': m.get('patient', ''),
            'lastMessage': m.get('message', '')[:80],
            'channel': m.get('channel', 'WhatsApp'),
            'status': m.get('status', 'Sent'),
        }
        for m in _mongo_list(db.messages, limit=20)
    ]

    audit = [
        {'actor': a.get('actor', a.get('user', '')), 'action': a.get('action', ''), 'timestamp': a.get('time', a.get('timestamp', ''))}
        for a in _mongo_list(db.audit_logs, {'scope': 'technician'})
    ]

    feed = [
        {'icon': f.get('icon', '📋'), 'text': f.get('text', ''), 'time': f.get('time', '')}
        for f in _mongo_list(db.activity_feed, {'scope': 'technician'})
    ]

    booking_count = len(bookings_raw)
    completed = sum(1 for b in bookings_raw if b.get('status') == 'Completed')
    pending = booking_count - completed
    delivered = _mongo_count(db.test_results)
    followups = _mongo_count(db.followups, {'status': 'Pending'})

    user = request.user
    return Response({
        'tasks': tasks,
        'samples': samples,
        'route_stops': route_stops,
        'comm_logs': comm_logs,
        'audit_log': audit,
        'activity_feed': feed,
        'metrics': {
            'today_collections': booking_count,
            'completed': completed,
            'pending': pending,
            'delivered': delivered,
            'followups': followups,
            'success_rate': round(completed / max(booking_count, 1) * 100),
        },
        'technician_name': user.get_full_name() or user.username,
    })


# ─── SUPER ADMIN ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def superadmin_dashboard_api(request):
    hospitals = _mongo_list(db.hospitals)
    total_patients = _mongo_count(db.patients)
    active_hospitals = sum(1 for h in hospitals if h.get('is_active'))
    total_care_gaps = _mongo_count(db.care_gaps, {'status': 'Open'})
    closed_care_gaps = _mongo_count(db.care_gaps, {'status': 'Closed'})
    total_messages = _mongo_count(db.messages)
    delivered = _mongo_count(db.messages, {'status': 'Delivered'})
    delivery_rate = round(delivered / max(total_messages, 1) * 100, 1)

    risk_critical = _mongo_count(db.patients, {'risk': 'Critical'})
    risk_high = _mongo_count(db.patients, {'risk': 'High'})
    risk_medium = _mongo_count(db.patients, {'risk': 'Medium'})
    risk_low = _mongo_count(db.patients, {'risk': 'Low'})

    tenants = [
        {
            'name': h.get('name', ''),
            'tenantId': h.get('tenant_id', ''),
            'plan': h.get('plan', 'Professional'),
            'patients': _mongo_count(db.patients, {'hospital': h.get('name', '')}),
            'doctors': _mongo_count(db.doctors, {'hospital': h.get('name', '')}),
            'status': 'Active' if h.get('is_active') else 'Inactive',
        }
        for h in hospitals
    ]

    users = [
        {
            'name': u.get('name', ''),
            'role': u.get('role', ''),
            'hospital': u.get('hospital', ''),
            'lastLogin': u.get('last_login', ''),
        }
        for u in _mongo_list(db.platform_users)
    ]

    global_patients = [
        {
            'id': p.get('patient_id', ''),
            'hospital': p.get('hospital', ''),
            'disease': p.get('disease', ''),
            'lastTest': p.get('last_test', ''),
            'risk': p.get('risk', 'Low'),
            'gap': p.get('care_gap', 'Open'),
        }
        for p in _mongo_list(db.patients, sort=[('overdue_days', -1)], limit=50)
    ]

    ai_decisions = [
        {
            'patient': d.get('patient', ''),
            'hospital': d.get('hospital', ''),
            'risk': d.get('risk', ''),
            'action': d.get('action', ''),
        }
        for d in _mongo_list(db.ai_decisions)
    ]

    msgs_out = [
        {'patient': m.get('patient', ''), 'hospital': m.get('hospital', ''),
         'channel': m.get('channel', ''), 'status': m.get('status', '')}
        for m in _mongo_list(db.messages)
    ]

    bookings_out = [
        {'patient': b.get('patient', ''), 'test': b.get('test', ''),
         'tech': b.get('technician', ''), 'status': b.get('status', '')}
        for b in _mongo_list(db.bookings)
    ]

    uploads = [
        {'hospital': u.get('hospital', ''), 'file': u.get('file', ''),
         'records': str(u.get('records', '')), 'date': u.get('date', '')}
        for u in _mongo_list(db.dataset_uploads)
    ]

    services = [
        {'service': s.get('service', s.get('name', '')), 'status': s.get('status', ''), 'ms': str(s.get('ms', s.get('latency', '')))}
        for s in _mongo_list(db.system_services)
    ]

    errors = [
        {'error': e.get('error', e.get('message', '')), 'module': e.get('module', ''),
         'time': e.get('time', e.get('timestamp', '')), 'status': e.get('status', '')}
        for e in _mongo_list(db.error_logs)
    ]

    billing = [
        {'hospital': b.get('hospital', ''), 'plan': b.get('plan', ''),
         'limit': str(b.get('limit', '')), 'status': b.get('status', '')}
        for b in _mongo_list(db.subscriptions)
    ]

    audit = [
        {'user': a.get('user', ''), 'action': a.get('action', ''),
         'hospital': a.get('hospital', ''), 'time': a.get('time', a.get('timestamp', ''))}
        for a in _mongo_list(db.audit_logs, {'scope': 'superadmin'})
    ]

    feed = [
        {'emoji': f.get('icon', f.get('emoji', '📋')), 'text': f.get('text', ''), 'time': f.get('time', '')}
        for f in _mongo_list(db.activity_feed, {'scope': 'superadmin'})
    ]

    infra = [
        {'service': s.get('service', s.get('name', '')), 'status': s.get('status', '')}
        for s in _mongo_list(db.system_services)
    ]

    protocols = _mongo_list(db.protocols)
    protocols_out = [
        [p.get('name', ''), p.get('status', '')]
        for p in protocols
    ]

    msg_replied = _mongo_count(db.messages, {'status': 'Replied'})
    msg_booked = _mongo_count(db.bookings)
    sent_pct = 100 if total_messages else 0
    replied_pct = round(msg_replied / max(total_messages, 1) * 100)
    booked_pct = round(msg_booked / max(total_messages, 1) * 100)

    return Response({
        'tenants': tenants,
        'users': users,
        'global_patients': global_patients,
        'ai_decisions': ai_decisions,
        'messages': msgs_out,
        'bookings': bookings_out,
        'uploads': uploads,
        'services': services,
        'errors': errors,
        'billing': billing,
        'audit_log': audit,
        'activity_feed': feed,
        'infra': infra,
        'protocols': protocols_out,
        'metrics': {
            'total_hospitals': len(hospitals),
            'active_hospitals': active_hospitals,
            'total_patients': total_patients,
            'care_gaps_open': total_care_gaps,
            'care_gaps_closed': closed_care_gaps,
            'total_messages': total_messages,
            'delivery_rate': delivery_rate,
            'risk_critical': risk_critical,
            'risk_high': risk_high,
            'risk_medium': risk_medium,
            'risk_low': risk_low,
            'sent_pct': sent_pct,
            'replied_pct': replied_pct,
            'booked_pct': booked_pct,
        },
        'admin_name': request.user.get_full_name() or request.user.username,
    })


# ─── Helpers ─────────────────────────────────────────────────────────
def _map_risk(raw: str) -> str:
    mapping = {'low': 'low', 'medium': 'medium', 'high': 'high', 'critical': 'critical'}
    return mapping.get(raw.lower(), 'low')


def _map_collection_status(raw: str) -> str:
    mapping = {
        'scheduled': 'scheduled', 'in progress': 'inProgress',
        'completed': 'completed', 'cancelled': 'cancelled',
    }
    return mapping.get(raw.lower(), 'scheduled')


def _map_sample_status(raw: str) -> str:
    mapping = {
        'pending': 'pending', 'collected': 'collected',
        'in transit': 'inTransit', 'delivered': 'delivered',
        'report finalised': 'reportFinalised',
    }
    return mapping.get(raw.lower(), 'pending')
