import json
from datetime import datetime

from django.contrib import messages as django_messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from config.db import db


def _redirect_for_role(user):
    """Return the correct redirect based on user role."""
    if user.is_superuser or user.role == 'platform_admin':
        return redirect('accounts:superadmin')
    if user.role == 'hospital_admin':
        return redirect('accounts:hospital_admin')
    if user.role == 'doctor':
        return redirect('accounts:doctor')
    if user.role == 'technician':
        return redirect('accounts:technician')
    # Fallback: go to root landing page instead of dashboard to avoid loop
    return redirect('index')


def index_view(request):
    return render(request, 'index.html')


def login_view(request):
    if request.user.is_authenticated:
        return _redirect_for_role(request.user)

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', '').strip()

        user = authenticate(request, username=email, password=password)
        if user is not None:
            if role and user.role != role:
                django_messages.error(request, 'Role does not match your account.')
            else:
                login(request, user)
                return _redirect_for_role(user)
        else:
            django_messages.error(request, 'Invalid email or password.')

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    response = redirect('accounts:login')
    response.delete_cookie('sessionid')
    response.delete_cookie('csrftoken')
    response.delete_cookie('messages')
    return response


@login_required
def dashboard_view(request):
    return _redirect_for_role(request.user)


# ─── helpers ───────────────────────────────────────────────────────────
def _mongo_list(collection, query=None, limit=0, sort=None):
    """Return a plain list of dicts from a MongoDB collection (no ObjectId)."""
    cursor = collection.find(query or {}, {'_id': 0})
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def _mongo_count(collection, query=None):
    """Return count of documents matching query."""
    return collection.count_documents(query or {})


# ─── SUPERADMIN ────────────────────────────────────────────────────────
@login_required
def superadmin_dashboard_view(request):
    if not (request.user.is_superuser or request.user.role == 'platform_admin'):
        return _redirect_for_role(request.user)

    hospitals = _mongo_list(db.hospitals)
    total_patients = _mongo_count(db.patients)
    active_hospitals = sum(1 for h in hospitals if h.get('is_active'))
    total_care_gaps = _mongo_count(db.care_gaps, {'status': 'Open'})
    closed_care_gaps = _mongo_count(db.care_gaps, {'status': 'Closed'})
    total_messages = _mongo_count(db.messages)
    delivered = _mongo_count(db.messages, {'status': 'Delivered'})
    delivery_rate = round(delivered / total_messages * 100, 1) if total_messages else 0
    risk_critical = _mongo_count(db.patients, {'risk': 'Critical'})
    risk_high = _mongo_count(db.patients, {'risk': 'High'})
    risk_medium = _mongo_count(db.patients, {'risk': 'Medium'})
    risk_low = _mongo_count(db.patients, {'risk': 'Low'})

    # Top 10 highest-risk patients (by risk_score descending)
    top_10_patients = list(db.patients.find(
        {'risk_score': {'$exists': True}},
        {'_id': 0, 'patient_id': 1, 'name': 1, 'disease': 1, 'risk': 1,
         'risk_score': 1, 'last_test': 1, 'last_result': 1, 'overdue_days': 1,
         'hospital': 1, 'age': 1, 'phone': 1, 'whatsapp_state': 1},
    ).sort('risk_score', -1).limit(10))
    msg_replied = _mongo_count(db.messages, {'status': 'Replied'})
    msg_booked = _mongo_count(db.bookings)
    sent_pct = 100 if total_messages else 0
    replied_pct = round(msg_replied / total_messages * 100) if total_messages else 0
    booked_pct = round(msg_booked / total_messages * 100) if total_messages else 0

    ctx = {
        'total_hospitals': len(hospitals),
        'active_hospitals': active_hospitals,
        'total_patients': f'{total_patients:,}',
        'total_patients_raw': total_patients,
        'hospitals': hospitals,
        'users': _mongo_list(db.platform_users),
        'patients': _mongo_list(db.patients, sort=[('overdue_days', -1)], limit=50),
        'care_gaps': _mongo_list(db.care_gaps, sort=[('overdue_days', -1)], limit=50),
        'messages': _mongo_list(db.messages),
        'bookings': _mongo_list(db.bookings),
        'ai_decisions': _mongo_list(db.ai_decisions),
        'feed': _mongo_list(db.activity_feed, {'scope': 'superadmin'}),
        'system_services': _mongo_list(db.system_services),
        'error_logs': _mongo_list(db.error_logs),
        'subscriptions': _mongo_list(db.subscriptions),
        'protocols': _mongo_list(db.protocols),
        'audit_logs': _mongo_list(db.audit_logs, {'scope': 'superadmin'}),
        'dataset_uploads': _mongo_list(db.dataset_uploads),
        'analytics': _mongo_list(db.analytics, {'scope': 'superadmin', 'label': {'$exists': True}}),
        'daily_messages': f'{total_messages:,}',
        'delivery_rate': delivery_rate,
        'care_gaps_today': f'{total_care_gaps:,}',
        'care_gaps_closed': f'{closed_care_gaps:,}',
        'admin_name': request.user.get_full_name() or request.user.username,
        'risk_critical': risk_critical,
        'risk_high': risk_high,
        'risk_medium': risk_medium,
        'risk_low': risk_low,
        'top_10_patients': top_10_patients,
        'sent_pct': sent_pct,
        'replied_pct': replied_pct,
        'booked_pct': booked_pct,
    }
    return render(request, 'superadmin.html', ctx)


# ─── HOSPITAL ADMIN ───────────────────────────────────────────────────
@login_required
def hospital_admin_view(request):
    if request.user.role != 'hospital_admin':
        return _redirect_for_role(request.user)

    total_patients = _mongo_count(db.patients)
    open_gaps = _mongo_count(db.care_gaps, {'status': 'Open'})
    closed_gaps = _mongo_count(db.care_gaps, {'status': 'Closed'})

    # Disease distribution for chart
    disease_counts = {}
    for d in db.patients.aggregate([
        {'$group': {'_id': '$disease', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 6},
    ]):
        disease_counts[d['_id']] = d['count']
    disease_labels = list(disease_counts.keys())
    disease_values = list(disease_counts.values())
    disease_max = max(disease_values) if disease_values else 1
    disease_pcts = [round(v / total_patients * 100) if total_patients else 0 for v in disease_values]
    disease_heights = [round(v / disease_max * 100) for v in disease_values]
    disease_data = [{'label': l, 'pct': p, 'height': h} for l, p, h in zip(disease_labels, disease_pcts, disease_heights)]

    # Hospital name from user's org or first hospital
    hospital_name = request.user.organization_id if hasattr(request.user, 'organization_id') and request.user.organization_id else ''
    if not hospital_name:
        h = db.hospitals.find_one({}, {'name': 1, '_id': 0})
        hospital_name = h.get('name', 'Hospital') if h else 'Hospital'

    ctx = {
        'patients': _mongo_list(db.patients, sort=[('overdue_days', -1)], limit=50),
        'doctors': _mongo_list(db.doctors),
        'technicians': _mongo_list(db.technicians),
        'care_gaps': _mongo_list(db.care_gaps, sort=[('overdue_days', -1)], limit=50),
        'bookings': _mongo_list(db.bookings),
        'messages': _mongo_list(db.messages),
        'protocols': _mongo_list(db.protocols),
        'feed': _mongo_list(db.activity_feed, {'scope': 'hospital_admin'}),
        'audit_logs': _mongo_list(db.audit_logs, {'scope': 'hospital_admin'}),
        'analytics': _mongo_list(db.analytics, {'scope': 'hospital_admin', 'label': {'$exists': True}}),
        'total_patients': f'{total_patients:,}',
        'care_gaps_open': f'{open_gaps:,}',
        'care_gaps_closed': f'{closed_gaps:,}',
        'admin_name': request.user.get_full_name() or request.user.username,
        'hospital_name': hospital_name,
        'disease_labels': disease_labels,
        'disease_pcts': disease_pcts,
        'disease_heights': disease_heights,
        'disease_data': disease_data,
    }
    return render(request, 'hospitaladmin.html', ctx)


# ─── DOCTOR ────────────────────────────────────────────────────────────
@login_required
def doctor_view(request):
    if request.user.role != 'doctor':
        return _redirect_for_role(request.user)

    total_patients = _mongo_count(db.patients)
    critical_alerts = _mongo_count(db.patients, {'risk': {'$in': ['High', 'Critical']}})
    open_gaps = _mongo_count(db.care_gaps, {'status': 'Open'})
    closed_gaps = _mongo_count(db.care_gaps, {'status': 'Closed'})
    risk_low = _mongo_count(db.patients, {'risk': 'Low'})
    risk_med = _mongo_count(db.patients, {'risk': 'Medium'})
    risk_high = _mongo_count(db.patients, {'risk': 'High'})
    risk_crit = _mongo_count(db.patients, {'risk': 'Critical'})
    risk_max = max(risk_low, risk_med, risk_high, risk_crit, 1)

    ctx = {
        'patients': _mongo_list(db.patients, sort=[('overdue_days', -1)], limit=50),
        'total_patients': f'{total_patients:,}',
        'critical_alerts': f'{critical_alerts:,}',
        'care_gaps': _mongo_list(db.care_gaps, sort=[('overdue_days', -1)], limit=50),
        'care_gaps_today': f'{open_gaps:,}',
        'care_gaps_closed': f'{closed_gaps:,}',
        'test_results': _mongo_list(db.test_results, {'scope': 'recent'}, limit=50),
        'test_history': _mongo_list(db.test_results, limit=10),
        'appointments': _mongo_list(db.appointments),
        'messages': _mongo_list(db.messages, limit=50),
        'feed': _mongo_list(db.activity_feed, {'scope': 'doctor'}),
        'audit_logs': _mongo_list(db.audit_logs, {'scope': 'doctor'}),
        'analytics': _mongo_list(db.analytics, {'scope': 'doctor', 'label': {'$exists': True}}),
        'doctor_name': request.user.get_full_name() or request.user.username,
        'doctor_initials': ''.join(w[0] for w in (request.user.get_full_name() or request.user.username).split()[:2]).upper(),
        'risk_low': risk_low,
        'risk_med': risk_med,
        'risk_high': risk_high,
        'risk_crit': risk_crit,
        'risk_low_pct': round(risk_low / risk_max * 100),
        'risk_med_pct': round(risk_med / risk_max * 100),
        'risk_high_pct': round(risk_high / risk_max * 100),
        'risk_crit_pct': round(risk_crit / risk_max * 100),
    }
    return render(request, 'doctor.html', ctx)


# ─── TECHNICIAN ────────────────────────────────────────────────────────
@login_required
def technician_view(request):
    if request.user.role != 'technician':
        return _redirect_for_role(request.user)

    booking_count = _mongo_count(db.bookings)
    completed_bookings = _mongo_count(db.bookings, {'status': 'Completed'})
    scheduled_bookings = _mongo_count(db.bookings, {'status': 'Scheduled'})
    delivered_count = _mongo_count(db.test_results)
    followup_pending = _mongo_count(db.followups, {'status': 'Pending'})

    # Build a patient lookup for enriching bookings
    patients_map = {}
    for p in db.patients.find({}, {'name': 1, 'disease': 1, 'age': 1, 'phone': 1,
                                    'patient_id': 1, 'hospital': 1, 'doctor': 1}):
        patients_map[p.get('name', '')] = p

    # Enrich bookings with patient details
    bookings_raw = _mongo_list(db.bookings)
    for b in bookings_raw:
        pinfo = patients_map.get(b.get('patient', ''), {})
        b['disease'] = pinfo.get('disease', '')
        b['age'] = pinfo.get('age', '')
        b['phone'] = pinfo.get('phone', '')
        b['patient_id'] = pinfo.get('patient_id', '')
        b['hospital'] = pinfo.get('hospital', b.get('hospital', ''))
        b['doctor'] = pinfo.get('doctor', '')

    ctx = {
        'today_collections': booking_count,
        'completed_count': completed_bookings,
        'pending_count': scheduled_bookings,
        'delivered_count': delivered_count,
        'followup_count': followup_pending,
        'success_rate': round(completed_bookings / booking_count * 100) if booking_count else 0,
        'bookings': bookings_raw,
        'messages': _mongo_list(db.messages),
        'test_results': _mongo_list(db.test_results),
        'followups': _mongo_list(db.followups),
        'feed': _mongo_list(db.activity_feed, {'scope': 'technician'}),
        'audit_logs': _mongo_list(db.audit_logs, {'scope': 'technician'}),
        'technician_name': request.user.get_full_name() or request.user.username,
        'technician_initials': ''.join(w[0] for w in (request.user.get_full_name() or request.user.username).split()[:2]).upper(),
        'technician_email': request.user.email or request.user.username,
    }
    return render(request, 'technician.html', ctx)


# ─── API ENDPOINTS (store records) ────────────────────────────────────
@login_required
def api_add_patient(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    name = request.POST.get('name', '').strip()
    disease = request.POST.get('disease', '').strip()
    phone = request.POST.get('phone', '').strip()
    if not name or not disease:
        return JsonResponse({'error': 'name and disease are required'}, status=400)
    last_id = db.patients.find_one(sort=[('patient_id', -1)], projection={'patient_id': 1, '_id': 0})
    next_num = int(last_id['patient_id'][1:]) + 1 if last_id else 1001
    doc = {
        'patient_id': f'P{next_num}',
        'name': name,
        'disease': disease,
        'phone': phone,
        'hospital': '',
        'last_test': 'N/A',
        'risk': 'Low',
        'care_gap': 'Open',
        'channel': 'WhatsApp',
        'doctor': '',
    }
    db.patients.insert_one(doc)
    return JsonResponse({'status': 'ok', 'patient_id': doc['patient_id']})


@login_required
def api_add_doctor(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    name = request.POST.get('name', '').strip()
    specialty = request.POST.get('specialty', '').strip()
    if not name:
        return JsonResponse({'error': 'name is required'}, status=400)
    db.doctors.insert_one({'name': name, 'specialty': specialty, 'patients': 0, 'status': 'Active'})
    return JsonResponse({'status': 'ok'})


@login_required
def api_add_booking(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    patient = request.POST.get('patient', '').strip()
    test = request.POST.get('test', '').strip()
    date = request.POST.get('date', '').strip()
    technician = request.POST.get('technician', '').strip()
    if not patient or not test:
        return JsonResponse({'error': 'patient and test are required'}, status=400)
    db.bookings.insert_one({'patient': patient, 'test': test, 'date': date, 'technician': technician, 'status': 'Scheduled'})
    return JsonResponse({'status': 'ok'})


@login_required
def api_add_appointment(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    patient = request.POST.get('patient', '').strip()
    purpose = request.POST.get('purpose', '').strip()
    date = request.POST.get('date', '').strip()
    if not patient:
        return JsonResponse({'error': 'patient is required'}, status=400)
    db.appointments.insert_one({'patient': patient, 'purpose': purpose, 'date': date, 'status': 'Scheduled'})
    return JsonResponse({'status': 'ok'})


@login_required
def api_add_followup(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    patient = request.POST.get('patient', '').strip()
    task = request.POST.get('task', '').strip()
    due_date = request.POST.get('due_date', '').strip()
    if not patient:
        return JsonResponse({'error': 'patient is required'}, status=400)
    db.followups.insert_one({'patient': patient, 'task': task, 'due_date': due_date, 'status': 'Pending'})
    return JsonResponse({'status': 'ok'})


@login_required
def api_send_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    patient = request.POST.get('patient', '').strip()
    channel = request.POST.get('channel', 'WhatsApp').strip()
    message = request.POST.get('message', '').strip()
    language = request.POST.get('language', 'en').strip()
    if not patient:
        return JsonResponse({'error': 'patient is required'}, status=400)

    # Translate if non-English language selected
    final_message = message
    if language and language != 'en':
        from services.message_generator import translate_message
        final_message = translate_message(message, language)

    # Attempt actual WhatsApp delivery if channel is WhatsApp
    twilio_sid = None
    delivery_status = 'Sent'
    if channel == 'WhatsApp':
        patient_doc = db.patients.find_one({'name': patient}, {'phone': 1, '_id': 0})
        phone = patient_doc.get('phone', '') if patient_doc else ''
        if phone:
            try:
                from integrations.twilio_service import send_whatsapp_message
                twilio_sid = send_whatsapp_message(phone, final_message)
                delivery_status = 'Delivered'
            except Exception as exc:
                delivery_status = 'Failed'

    from services.message_generator import SUPPORTED_LANGUAGES
    lang_name = SUPPORTED_LANGUAGES.get(language, 'English')
    db.messages.insert_one({
        'patient': patient, 'hospital': '', 'channel': channel,
        'message': final_message, 'original_message': message if language != 'en' else '',
        'language': lang_name, 'disease': '', 'status': delivery_status,
        'twilio_sid': twilio_sid or '',
        'sent_at': datetime.utcnow().isoformat(),
    })
    db.audit_logs.insert_one({
        'scope': 'technician', 'action': f'Sent {channel} message ({lang_name})',
        'target': patient, 'time': 'Just now',
    })
    return JsonResponse({'status': 'ok', 'delivered': delivery_status, 'language': lang_name})


@login_required
def api_add_test_result(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    patient = request.POST.get('patient', '').strip()
    test = request.POST.get('test', '').strip()
    result = request.POST.get('result', '').strip()
    if not test:
        return JsonResponse({'error': 'test is required'}, status=400)
    db.test_results.insert_one({
        'patient': patient, 'test': test, 'result': result,
        'date': 'Today', 'notes': '', 'scope': 'recent',
    })
    return JsonResponse({'status': 'ok'})


# ─── SUPERADMIN CRUD – TENANTS ─────────────────────────────────────────
def _require_platform_admin(user):
    return user.is_superuser or user.role == 'platform_admin'


@login_required
@require_POST
def api_add_tenant(request):
    if not _require_platform_admin(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    name = data.get('name', '').strip()
    tenant_id = data.get('tenant_id', '').strip()
    plan = data.get('plan', 'Pro').strip()
    if not name or not tenant_id:
        return JsonResponse({'error': 'name and tenant_id are required'}, status=400)
    if db.hospitals.find_one({'tenant_id': tenant_id}):
        return JsonResponse({'error': 'tenant_id already exists'}, status=400)
    doc = {
        'name': name,
        'tenant_id': tenant_id,
        'plan': plan,
        'patients': 0,
        'doctors_count': 0,
        'status': 'Active',
        'is_active': True,
        'created_at': datetime.utcnow().isoformat(),
    }
    db.hospitals.insert_one(doc)
    db.audit_logs.insert_one({
        'scope': 'superadmin', 'user': request.user.username,
        'action': f'Created tenant {name}', 'hospital': name,
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
    })
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def api_edit_tenant(request):
    if not _require_platform_admin(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    tenant_id = data.get('tenant_id', '').strip()
    if not tenant_id:
        return JsonResponse({'error': 'tenant_id is required'}, status=400)
    updates = {}
    for field in ('name', 'plan', 'status'):
        val = data.get(field, '').strip()
        if val:
            updates[field] = val
    if 'status' in updates:
        updates['is_active'] = updates['status'] == 'Active'
    if not updates:
        return JsonResponse({'error': 'No fields to update'}, status=400)
    result = db.hospitals.update_one({'tenant_id': tenant_id}, {'$set': updates})
    if result.matched_count == 0:
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    db.audit_logs.insert_one({
        'scope': 'superadmin', 'user': request.user.username,
        'action': f'Edited tenant {tenant_id}', 'hospital': updates.get('name', tenant_id),
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
    })
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def api_delete_tenant(request):
    if not _require_platform_admin(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    tenant_id = data.get('tenant_id', '').strip()
    if not tenant_id:
        return JsonResponse({'error': 'tenant_id is required'}, status=400)
    result = db.hospitals.delete_one({'tenant_id': tenant_id})
    if result.deleted_count == 0:
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    db.audit_logs.insert_one({
        'scope': 'superadmin', 'user': request.user.username,
        'action': f'Deleted tenant {tenant_id}', 'hospital': tenant_id,
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
    })
    return JsonResponse({'status': 'ok'})


# ─── SUPERADMIN CRUD – USERS ──────────────────────────────────────────
@login_required
@require_POST
def api_create_user(request):
    if not _require_platform_admin(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'doctor').strip()
    hospital = data.get('hospital', '').strip()
    if not name or not email or not password:
        return JsonResponse({'error': 'name, email and password are required'}, status=400)
    if User.objects.filter(username=email).exists():
        return JsonResponse({'error': 'User with this email already exists'}, status=400)
    # Create Django auth user
    user = User.objects.create_user(username=email, email=email, password=password, role=role)
    parts = name.split(' ', 1)
    user.first_name = parts[0]
    user.last_name = parts[1] if len(parts) > 1 else ''
    user.save()
    # Store in MongoDB platform_users
    db.platform_users.insert_one({
        'name': name,
        'email': email,
        'role': role,
        'hospital': hospital,
        'status': 'Active',
        'last_login': 'Never',
    })
    db.audit_logs.insert_one({
        'scope': 'superadmin', 'user': request.user.username,
        'action': f'Created user {email} ({role})', 'hospital': hospital,
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
    })
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def api_edit_user(request):
    if not _require_platform_admin(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    email = data.get('email', '').strip()
    if not email:
        return JsonResponse({'error': 'email is required'}, status=400)
    updates = {}
    for field in ('name', 'role', 'hospital', 'status'):
        val = data.get(field, '').strip()
        if val:
            updates[field] = val
    if not updates:
        return JsonResponse({'error': 'No fields to update'}, status=400)
    result = db.platform_users.update_one({'email': email}, {'$set': updates})
    if result.matched_count == 0:
        return JsonResponse({'error': 'User not found'}, status=404)
    # Also update Django user if role changed
    try:
        django_user = User.objects.get(username=email)
        if 'role' in updates:
            django_user.role = updates['role']
        if 'name' in updates:
            parts = updates['name'].split(' ', 1)
            django_user.first_name = parts[0]
            django_user.last_name = parts[1] if len(parts) > 1 else ''
        django_user.save()
    except User.DoesNotExist:
        pass
    db.audit_logs.insert_one({
        'scope': 'superadmin', 'user': request.user.username,
        'action': f'Edited user {email}', 'hospital': updates.get('hospital', ''),
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
    })
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def api_delete_user(request):
    if not _require_platform_admin(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    email = data.get('email', '').strip()
    if not email:
        return JsonResponse({'error': 'email is required'}, status=400)
    if email == request.user.username:
        return JsonResponse({'error': 'Cannot delete yourself'}, status=400)
    result = db.platform_users.delete_one({'email': email})
    # Also remove Django user
    User.objects.filter(username=email).delete()
    if result.deleted_count == 0:
        return JsonResponse({'error': 'User not found in MongoDB'}, status=404)
    db.audit_logs.insert_one({
        'scope': 'superadmin', 'user': request.user.username,
        'action': f'Deleted user {email}', 'hospital': '',
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
    })
    return JsonResponse({'status': 'ok'})


# ─── PIPELINE & WHATSAPP TRIGGERS ─────────────────────────────────────
@login_required
@require_POST
def api_run_pipeline(request):
    """Manually trigger the daily risk/care-gap/messaging pipeline."""
    if not _require_platform_admin(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # Check if already running
    state = db.pipeline_state.find_one({'_id': 'current'})
    if state and state.get('status') == 'running':
        return JsonResponse({'status': 'already_running', 'stage': state.get('stage', ''), 'progress': state.get('progress', 0)})

    try:
        from tasks.daily_monitoring import run_daily_pipeline
        result = run_daily_pipeline.delay()
        return JsonResponse({'status': 'ok', 'task_id': str(result.id)})
    except Exception:
        # Celery/Redis not available — run in a background thread
        import threading
        from tasks.daily_monitoring import run_daily_pipeline

        def _run():
            try:
                run_daily_pipeline()
            except Exception as exc:
                db.pipeline_state.update_one(
                    {'_id': 'current'},
                    {'$set': {'status': 'failed', 'stage': str(exc), 'progress': 0}},
                    upsert=True,
                )

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return JsonResponse({'status': 'ok', 'ran_async': True})


@login_required
@require_POST
def api_send_whatsapp(request):
    """Send WhatsApp to a single patient from the dashboard."""
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    patient_id = data.get('patient_id', '').strip()
    custom_message = data.get('message', '').strip() or None
    if not patient_id:
        return JsonResponse({'error': 'patient_id is required'}, status=400)
    try:
        from tasks.message_dispatcher import send_single_whatsapp
        result = send_single_whatsapp.delay(patient_id, custom_message)
        return JsonResponse({'status': 'ok', 'task_id': str(result.id)})
    except Exception:
        from tasks.message_dispatcher import send_single_whatsapp
        result = send_single_whatsapp(patient_id, custom_message)
        return JsonResponse(result)


# ─── WHATSAPP INCOMING WEBHOOK (Twilio) ────────────────────────────────
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse


@csrf_exempt
def whatsapp_incoming_webhook(request):
    """Receive incoming WhatsApp messages from patients via Twilio webhook.
    Handles language selection, appointment booking, and general queries.
    Responds with TwiML XML."""
    if request.method != 'POST':
        return HttpResponse('<Response></Response>', content_type='text/xml')

    body = request.POST.get('Body', '').strip()
    from_number = request.POST.get('From', '').replace('whatsapp:', '')
    if not body or not from_number:
        return HttpResponse(
            '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            content_type='text/xml',
        )

    # Language menu mapping (must match pipeline's LANGUAGE_MENU)
    LANGUAGE_MENU = {
        '1': 'en', '2': 'hi', '3': 'ta', '4': 'te', '5': 'kn', '6': 'ml',
    }
    LANGUAGE_NAMES = {
        'en': 'English', 'hi': 'Hindi', 'ta': 'Tamil',
        'te': 'Telugu', 'kn': 'Kannada', 'ml': 'Malayalam',
    }

    # Look up patient by phone number
    # Prefer the patient currently awaiting language selection (pipeline target)
    projection = {
        '_id': 0, 'name': 1, 'patient_id': 1, 'disease': 1, 'phone': 1,
        'hospital': 1, 'doctor': 1, 'last_test': 1, 'last_result': 1,
        'risk': 1, 'whatsapp_state': 1, 'preferred_language': 1,
        'age': 1, 'risk_score': 1,
    }
    phone_regex = {'$regex': from_number[-10:]}
    patient = db.patients.find_one(
        {'phone': phone_regex, 'whatsapp_state': 'awaiting_language'},
        projection,
    )
    if not patient:
        # Fall back: patient with active conversation state
        patient = db.patients.find_one(
            {'phone': phone_regex, 'whatsapp_state': 'active'},
            projection,
        )
    if not patient:
        # Fall back: any patient with this phone, newest first
        patient = db.patients.find_one(
            {'phone': phone_regex},
            projection,
            sort=[('_id', -1)],
        )

    patient_name = patient.get('name', 'Patient') if patient else 'Patient'
    patient_id = patient.get('patient_id', '') if patient else ''
    whatsapp_state = patient.get('whatsapp_state', '') if patient else ''
    patient_lang = patient.get('preferred_language', 'en') if patient else 'en'

    # Log the incoming message
    db.messages.insert_one({
        'patient': patient_name,
        'patient_id': patient_id,
        'channel': 'WhatsApp',
        'message': body,
        'language': patient_lang,
        'status': 'Received',
        'direction': 'inbound',
        'from_number': from_number,
        'sent_at': datetime.utcnow().isoformat(),
    })

    reply = ''

    # ── STEP A: Handle language selection (patient is awaiting_language) ──
    if whatsapp_state == 'awaiting_language' and body.strip() in LANGUAGE_MENU:
        chosen_code = LANGUAGE_MENU[body.strip()]
        chosen_name = LANGUAGE_NAMES.get(chosen_code, 'English')

        # Save language preference and move to active state
        db.patients.update_one(
            {'patient_id': patient_id},
            {'$set': {
                'preferred_language': chosen_code,
                'whatsapp_state': 'active',
            }}
        )
        patient_lang = chosen_code

        # Build the detailed health message in English first
        disease = patient.get('disease', 'your condition')
        last_test = patient.get('last_test', 'test')
        last_result = patient.get('last_result', 'N/A')
        risk = patient.get('risk', 'Unknown')
        age = patient.get('age', '')
        hospital = patient.get('hospital', '')

        from services.message_generator import generate_message, translate_message
        health_msg = generate_message(patient, risk)

        # Add booking prompt
        health_msg += (
            "\n\n📅 Would you like to schedule a test appointment?\n"
            "Reply *YES* to book an appointment.\n"
            "Reply *CANCEL* anytime to cancel."
        )

        # Translate to chosen language if not English
        if chosen_code != 'en':
            health_msg = translate_message(health_msg, chosen_code)

        reply = f"✅ Language set to *{chosen_name}*\n\n{health_msg}"

        # Log activity
        db.activity_feed.insert_one({
            'scope': 'technician', 'icon': '🌐',
            'text': f'{patient_name} selected {chosen_name} as preferred language via WhatsApp',
            'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
        })

    else:
        # ── Normal conversation flow (language already selected) ──
        # Use AI to detect intent and language
        from services.message_generator import detect_language_and_intent, translate_message
        parsed = detect_language_and_intent(body)
        intent = parsed.get('intent', 'query')
        detected_lang = parsed.get('language', 'en')
        extracted_date = parsed.get('date')
        extracted_test = parsed.get('test')

        # Use patient's stored language preference if set, otherwise detected
        if patient_lang and patient_lang != 'en':
            lang = patient_lang
        else:
            lang = detected_lang

        if intent in ('confirm_yes', 'book_appointment'):
            # Create a booking via WhatsApp
            if not extracted_date:
                from datetime import timedelta
                tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
                extracted_date = tomorrow

            test_name = extracted_test or (patient.get('last_test', 'Routine Check') if patient else 'Routine Check')
            hospital = patient.get('hospital', '') if patient else ''
            doctor = patient.get('doctor', '') if patient else ''

            booking_doc = {
                'patient': patient_name,
                'patient_id': patient_id,
                'test': test_name,
                'date': extracted_date,
                'hospital': hospital,
                'doctor': doctor,
                'status': 'Scheduled',
                'source': 'WhatsApp',
                'phone': from_number,
                'created_at': datetime.utcnow().isoformat(),
            }
            db.bookings.insert_one(booking_doc)

            # Log activity
            db.activity_feed.insert_one({
                'scope': 'technician', 'icon': '📅',
                'text': f'{patient_name} booked appointment via WhatsApp for {extracted_date}',
                'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            })
            db.audit_logs.insert_one({
                'scope': 'technician',
                'action': 'WhatsApp Booking Created',
                'target': patient_name,
                'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            })

            reply = (
                f"✅ Appointment Confirmed!\n\n"
                f"Patient: {patient_name}\n"
                f"Test: {test_name}\n"
                f"Date: {extracted_date}\n"
                f"Hospital: {hospital or 'Will be assigned'}\n\n"
                f"A technician will contact you to confirm the time. "
                f"Reply CANCEL to cancel this appointment."
            )

        elif intent == 'cancel':
            # Cancel the most recent scheduled booking for this patient
            result = db.bookings.find_one_and_update(
                {'patient': patient_name, 'status': 'Scheduled'},
                {'$set': {'status': 'Cancelled'}},
                sort=[('_id', -1)],
            )
            if result:
                reply = f"❌ Your upcoming appointment has been cancelled.\n\nReply YES anytime to book a new one."
                db.activity_feed.insert_one({
                    'scope': 'technician', 'icon': '❌',
                    'text': f'{patient_name} cancelled appointment via WhatsApp',
                    'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                })
            else:
                reply = "You don't have any upcoming appointments to cancel."

        else:
            # General query — use AI to respond helpfully
            from integrations.llama_service import generate_ai_response
            disease = patient.get('disease', '') if patient else ''
            ai_prompt = (
                f"You are MediSynC, a friendly healthcare WhatsApp assistant. "
                f"A patient named {patient_name}"
                f"{' with ' + disease if disease else ''} sent this message: \"{body}\"\n\n"
                f"Reply helpfully in 2-3 sentences. If they seem to want an appointment, "
                f"tell them to reply YES to book one. Keep it warm and concise."
            )
            reply = generate_ai_response(ai_prompt)

        # Translate reply to patient's preferred language
        if lang and lang != 'en':
            reply = translate_message(reply, lang)

    # Log outbound reply
    db.messages.insert_one({
        'patient': patient_name,
        'patient_id': patient_id,
        'channel': 'WhatsApp',
        'message': reply[:500],
        'language': patient_lang,
        'status': 'Delivered',
        'direction': 'outbound',
        'sent_at': datetime.utcnow().isoformat(),
    })

    # Escape XML special characters in reply
    from xml.sax.saxutils import escape as xml_escape
    safe_reply = xml_escape(reply)
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe_reply}</Message></Response>'
    return HttpResponse(twiml, content_type='text/xml')


@login_required
@require_POST
def api_translate_preview(request):
    """Preview a translated message before sending."""
    message = request.POST.get('message', '').strip()
    language = request.POST.get('language', 'en').strip()
    if not message:
        return JsonResponse({'error': 'message is required'}, status=400)
    if language == 'en':
        return JsonResponse({'translated': message, 'language': 'English'})
    from services.message_generator import translate_message, SUPPORTED_LANGUAGES
    translated = translate_message(message, language)
    lang_name = SUPPORTED_LANGUAGES.get(language, 'English')
    return JsonResponse({'translated': translated, 'language': lang_name})


@login_required
def api_pipeline_status(request):
    """Return latest pipeline stats, run state, and recent activity feed."""
    stats = {
        'total_patients': db.patients.count_documents({}),
        'critical': db.patients.count_documents({'risk': 'Critical'}),
        'high': db.patients.count_documents({'risk': 'High'}),
        'medium': db.patients.count_documents({'risk': 'Medium'}),
        'low': db.patients.count_documents({'risk': 'Low'}),
        'open_gaps': db.care_gaps.count_documents({'status': 'Open'}),
        'closed_gaps': db.care_gaps.count_documents({'status': 'Closed'}),
        'messages_sent': db.messages.count_documents({'status': 'Delivered'}),
        'messages_failed': db.messages.count_documents({'status': 'Failed'}),
    }

    # Pipeline run state
    state = db.pipeline_state.find_one({'_id': 'current'})
    if state:
        stats['pipeline_status'] = state.get('status', 'idle')
        stats['pipeline_stage'] = state.get('stage', '')
        stats['pipeline_progress'] = state.get('progress', 0)
        stats['pipeline_started'] = state.get('started_at', '')
        stats['pipeline_completed'] = state.get('completed_at', '')
    else:
        stats['pipeline_status'] = 'idle'

    # Recent activity feed (latest 10, sorted by _id descending for natural insertion order)
    feed_items = list(db.activity_feed.find(
        {'scope': 'superadmin'},
        {'_id': 0, 'icon': 1, 'text': 1, 'time': 1},
    ).sort('_id', -1).limit(10))
    stats['feed'] = feed_items

    return JsonResponse(stats)


@login_required
def api_hospital_feed(request):
    """Return latest hospital-admin activity feed and disease distribution."""
    # Activity feed
    feed_items = list(db.activity_feed.find(
        {'scope': 'hospital_admin'},
        {'_id': 0, 'icon': 1, 'text': 1, 'time': 1},
    ).sort('_id', -1).limit(10))

    # Disease distribution
    total_patients = db.patients.count_documents({})
    disease_counts = {}
    for d in db.patients.aggregate([
        {'$group': {'_id': '$disease', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 6},
    ]):
        disease_counts[d['_id']] = d['count']
    disease_values = list(disease_counts.values())
    disease_max = max(disease_values) if disease_values else 1
    disease_data = [
        {
            'label': label,
            'pct': round(count / total_patients * 100) if total_patients else 0,
            'height': round(count / disease_max * 100),
        }
        for label, count in disease_counts.items()
    ]

    return JsonResponse({'feed': feed_items, 'disease_data': disease_data})


@login_required
def api_doctor_feed(request):
    """Return latest doctor activity feed and caseload distribution."""
    feed_items = list(db.activity_feed.find(
        {'scope': 'doctor'},
        {'_id': 0, 'icon': 1, 'text': 1, 'time': 1},
    ).sort('_id', -1).limit(10))

    risk_low = db.patients.count_documents({'risk': 'Low'})
    risk_med = db.patients.count_documents({'risk': 'Medium'})
    risk_high = db.patients.count_documents({'risk': 'High'})
    risk_crit = db.patients.count_documents({'risk': 'Critical'})
    risk_max = max(risk_low, risk_med, risk_high, risk_crit, 1)

    return JsonResponse({
        'feed': feed_items,
        'caseload': {
            'low_pct': round(risk_low / risk_max * 100),
            'med_pct': round(risk_med / risk_max * 100),
            'high_pct': round(risk_high / risk_max * 100),
            'crit_pct': round(risk_crit / risk_max * 100),
        },
    })


@login_required
def api_technician_feed(request):
    """Return latest technician activity feed and metrics."""
    feed_items = list(db.activity_feed.find(
        {'scope': 'technician'},
        {'_id': 0, 'icon': 1, 'text': 1, 'time': 1},
    ).sort('_id', -1).limit(10))

    return JsonResponse({
        'feed': feed_items,
        'metrics': {
            'today_collections': db.bookings.count_documents({}),
            'completed': db.bookings.count_documents({'status': 'Completed'}),
            'pending': db.bookings.count_documents({'status': 'Scheduled'}),
            'delivered': db.test_results.count_documents({}),
            'followups': db.followups.count_documents({'status': 'Pending'}),
        },
    })


@login_required
@require_POST
def api_update_booking_status(request):
    """Update a booking's status (e.g. Scheduled → In Progress → Completed)."""
    patient = request.POST.get('patient', '').strip()
    status = request.POST.get('status', '').strip()
    if not patient or not status:
        return JsonResponse({'error': 'patient and status required'}, status=400)
    allowed = ('Scheduled', 'In Progress', 'Completed')
    if status not in allowed:
        return JsonResponse({'error': f'status must be one of {allowed}'}, status=400)
    result = db.bookings.update_one({'patient': patient}, {'$set': {'status': status}})
    if result.matched_count == 0:
        return JsonResponse({'error': 'Booking not found'}, status=404)
    db.audit_logs.insert_one({
        'scope': 'technician',
        'action': f'Updated booking status to {status}',
        'target': patient,
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
    })
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def api_update_sample_status(request):
    """Update a test result sample status (Collected → In Transit → Delivered)."""
    patient = request.POST.get('patient', '').strip()
    status = request.POST.get('status', '').strip()
    if not patient or not status:
        return JsonResponse({'error': 'patient and status required'}, status=400)
    allowed = ('Collected', 'In Transit', 'Delivered')
    if status not in allowed:
        return JsonResponse({'error': f'status must be one of {allowed}'}, status=400)
    result = db.test_results.update_one({'patient': patient}, {'$set': {'status': status}})
    if result.matched_count == 0:
        return JsonResponse({'error': 'Sample not found'}, status=404)
    db.audit_logs.insert_one({
        'scope': 'technician',
        'action': f'Sample status → {status}',
        'target': patient,
        'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
    })
    return JsonResponse({'status': 'ok'})
