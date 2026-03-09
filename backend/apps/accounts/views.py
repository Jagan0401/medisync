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
    if user.role in ('coordinator', 'technician'):
        return redirect('accounts:coordinator')
    # Fallback: go to root landing page instead of dashboard to avoid loop
    return redirect('index')


def index_view(request):
    return render(request, 'index.html')


def login_view(request):
    if request.user.is_authenticated:
        return _redirect_for_role(request.user)

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return _redirect_for_role(user)
        else:
            django_messages.error(request, 'Invalid email or password.')

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


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

    ctx = {
        'total_hospitals': len(hospitals),
        'active_hospitals': active_hospitals,
        'total_patients': f'{total_patients:,}',
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
        'daily_messages': f'{_mongo_count(db.messages):,}',
        'care_gaps_today': f'{total_care_gaps:,}',
        'care_gaps_closed': f'{closed_care_gaps:,}',
    }
    return render(request, 'superadmin.html', ctx)


# ─── HOSPITAL ADMIN ───────────────────────────────────────────────────
@login_required
def hospital_admin_view(request):
    if request.user.role != 'hospital_admin':
        return _redirect_for_role(request.user)

    total_patients = _mongo_count(db.patients)

    ctx = {
        'patients': _mongo_list(db.patients, sort=[('overdue_days', -1)], limit=50),
        'doctors': _mongo_list(db.doctors),
        'technicians': _mongo_list(db.technicians),
        'coordinators': _mongo_list(db.coordinators),
        'care_gaps': _mongo_list(db.care_gaps, sort=[('overdue_days', -1)], limit=50),
        'bookings': _mongo_list(db.bookings),
        'messages': _mongo_list(db.messages),
        'protocols': _mongo_list(db.protocols),
        'feed': _mongo_list(db.activity_feed, {'scope': 'hospital_admin'}),
        'audit_logs': _mongo_list(db.audit_logs, {'scope': 'hospital_admin'}),
        'analytics': _mongo_list(db.analytics, {'scope': 'hospital_admin', 'label': {'$exists': True}}),
        'total_patients': f'{total_patients:,}',
        'admin_name': request.user.get_full_name() or request.user.username,
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
        'feed': _mongo_list(db.activity_feed, {'scope': 'doctor'}),
        'audit_logs': _mongo_list(db.audit_logs, {'scope': 'doctor'}),
        'analytics': _mongo_list(db.analytics, {'scope': 'doctor', 'label': {'$exists': True}}),
        'doctor_name': request.user.get_full_name() or request.user.username,
        'doctor_initials': ''.join(w[0] for w in (request.user.get_full_name() or request.user.username).split()[:2]).upper(),
    }
    return render(request, 'doctor.html', ctx)


# ─── COORDINATOR ───────────────────────────────────────────────────────
@login_required
def coordinator_view(request):
    if request.user.role not in ('coordinator', 'technician'):
        return _redirect_for_role(request.user)

    total_patients = _mongo_count(db.patients)
    open_gaps = _mongo_count(db.care_gaps, {'status': 'Open'})
    msg_count = _mongo_count(db.messages)
    booking_count = _mongo_count(db.bookings)
    followup_pending = _mongo_count(db.followups, {'status': 'Pending'})

    ctx = {
        'patients': _mongo_list(db.patients, sort=[('overdue_days', -1)], limit=50),
        'assigned_patients': f'{total_patients:,}',
        'gap_alerts': f'{open_gaps:,}',
        'msgs_sent': msg_count,
        'booked_slots': booking_count,
        'followup_count': followup_pending,
        'care_gaps': _mongo_list(db.care_gaps, sort=[('overdue_days', -1)], limit=50),
        'messages': _mongo_list(db.messages),
        'bookings': _mongo_list(db.bookings),
        'technicians': _mongo_list(db.technicians),
        'followups': _mongo_list(db.followups),
        'feed': _mongo_list(db.activity_feed, {'scope': 'coordinator'}),
        'audit_logs': _mongo_list(db.audit_logs, {'scope': 'coordinator'}),
        'coordinator_name': request.user.get_full_name() or request.user.username,
        'coordinator_initials': ''.join(w[0] for w in (request.user.get_full_name() or request.user.username).split()[:2]).upper(),
    }
    return render(request, 'coordinator.html', ctx)


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
    if not patient:
        return JsonResponse({'error': 'patient is required'}, status=400)
    db.messages.insert_one({
        'patient': patient, 'hospital': '', 'channel': channel,
        'message': message, 'disease': '', 'status': 'Sent',
    })
    db.audit_logs.insert_one({
        'scope': 'coordinator', 'action': f'Sent {channel} message',
        'target': patient, 'time': 'Just now',
    })
    return JsonResponse({'status': 'ok'})


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
    try:
        from tasks.daily_monitoring import run_daily_pipeline
        result = run_daily_pipeline.delay()
        return JsonResponse({'status': 'ok', 'task_id': str(result.id)})
    except Exception as exc:
        # If Redis/Celery isn't running, run synchronously
        from tasks.daily_monitoring import run_daily_pipeline
        stats = run_daily_pipeline()
        return JsonResponse({'status': 'ok', 'ran_sync': True, 'stats': stats})


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


@login_required
def api_pipeline_status(request):
    """Return latest pipeline stats for the dashboard."""
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
    return JsonResponse(stats)
