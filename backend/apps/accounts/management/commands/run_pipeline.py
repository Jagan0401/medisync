"""
MediSynC Startup Pipeline
==========================
Django management command that runs automatically on server start.

Steps:
  1. Generate random patients (default phone: +916385438323)
  2. Run risk engine — categorize Critical/High/Medium/Low
  3. Display Top 10 highest-risk patients with full details
  4. Send ONE WhatsApp message to the highest-risk patient
     - English base message with language selection menu
     - Patient replies 1-6 to pick language, then conversation continues in that language
  5. Log everything to activity_feed and audit_logs (no auto-bookings)
"""

import random
import logging
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s')
logger = logging.getLogger('pipeline')


# ─── Indian names / diseases for random generation ──────────────────
FIRST_NAMES = [
    'Arun', 'Priya', 'Vikram', 'Lakshmi', 'Suresh', 'Deepa', 'Karthik',
    'Ananya', 'Rajesh', 'Meena', 'Sanjay', 'Divya', 'Ganesh', 'Kavitha',
    'Mohan', 'Sneha', 'Ramesh', 'Pooja', 'Venkat', 'Swathi',
]
LAST_NAMES = [
    'Kumar', 'Sharma', 'Patel', 'Iyer', 'Reddy', 'Nair', 'Rao',
    'Singh', 'Das', 'Verma', 'Gupta', 'Joshi', 'Pillai', 'Menon',
]
DISEASES = ['Diabetes', 'Hypertension', 'CKD', 'Hypothyroidism', 'Cardiac', 'Anemia']
HOSPITALS = ['Apollo Chennai', 'Fortis Bangalore', 'GlobalCare Delhi', 'MedLife Hyderabad', 'HealthFirst Pune']
DOCTORS = ['Dr. Rahul', 'Dr. Meera', 'Dr. Kavita', 'Dr. Arjun', 'Dr. Priya']
TESTS_BY_DISEASE = {
    'Diabetes': 'HbA1c',
    'Hypertension': 'BP Panel',
    'CKD': 'Creatinine',
    'Hypothyroidism': 'TSH',
    'Cardiac': 'Lipid Profile',
    'Anemia': 'CBC',
}
# Result ranges that produce different risk levels
RESULTS_BY_DISEASE = {
    'Diabetes':       {'Critical': '11.2%', 'High': '8.9%', 'Medium': '7.1%', 'Low': '5.8%'},
    'Hypertension':   {'Critical': '185/110', 'High': '165/95', 'Medium': '145/90', 'Low': '128/82'},
    'CKD':            {'Critical': '4.5', 'High': '3.0', 'Medium': '1.8', 'Low': '1.1'},
    'Hypothyroidism': {'Critical': '12.0', 'High': '8.0', 'Medium': '5.5', 'Low': '3.2'},
    'Cardiac':        {'Critical': '260', 'High': '215', 'Medium': '185', 'Low': '150'},
    'Anemia':         {'Critical': '6.0', 'High': '8.5', 'Medium': '10.0', 'Low': '13.5'},
}
DEFAULT_PHONE = '+916385438323'
SECOND_PHONE = '+918056289009'

# Language menu shown to the patient (6 options)
LANGUAGE_MENU = {
    '1': 'en',
    '2': 'hi',
    '3': 'ta',
    '4': 'te',
    '5': 'kn',
    '6': 'ml',
}
LANGUAGE_MENU_TEXT = (
    "1. English\n"
    "2. हिन्दी (Hindi)\n"
    "3. தமிழ் (Tamil)\n"
    "4. తెలుగు (Telugu)\n"
    "5. ಕನ್ನಡ (Kannada)\n"
    "6. മലയാളം (Malayalam)"
)


class Command(BaseCommand):
    help = 'Run the MediSynC pipeline: generate patients → analyze → display top 10 → message highest risk'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=5, help='Number of random patients to add')
        parser.add_argument('--phone', type=str, default=DEFAULT_PHONE, help='Default phone for new patients')
        parser.add_argument('--dry-run', action='store_true', help='Skip actual WhatsApp sending')

    def handle(self, *args, **options):
        count = options['count']
        phone = options['phone']
        dry_run = options['dry_run']

        self.stdout.write(self.style.WARNING(
            '\n'
            '╔══════════════════════════════════════════════════════════════╗\n'
            '║           MediSynC AI Pipeline — Starting...                ║\n'
            '╚══════════════════════════════════════════════════════════════╝\n'
        ))

        # Late imports so Django is fully set up
        from config.db import db
        from services.risk_engine import calculate_risk, calculate_risk_score
        from services.care_gap_engine import detect_care_gap
        from services.message_generator import generate_message, SUPPORTED_LANGUAGES

        now = datetime.utcnow()

        # ═══════════════════════════════════════════════════════════
        # STEP 1: Generate random patients
        # ═══════════════════════════════════════════════════════════
        self.stdout.write(self.style.HTTP_INFO('\n── STEP 1: Generating %d random patients ──' % count))

        last_patient = db.patients.find_one(sort=[('patient_id', -1)])
        if last_patient and last_patient.get('patient_id', '').startswith('P'):
            try:
                next_num = int(last_patient['patient_id'][1:]) + 1
            except ValueError:
                next_num = 90001
        else:
            next_num = 90001

        new_patients = []
        for i in range(count):
            disease = random.choice(DISEASES)
            # Weighted risk: more chance of High/Critical for pipeline demo
            risk_tier = random.choices(
                ['Critical', 'High', 'Medium', 'Low'],
                weights=[25, 35, 25, 15],
                k=1
            )[0]
            result = RESULTS_BY_DISEASE[disease][risk_tier]
            overdue = random.randint(30, 250) if risk_tier in ('Critical', 'High') else random.randint(0, 90)
            age = random.randint(30, 75)

            patient = {
                'patient_id': f'P{next_num + i:05d}',
                'name': f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}',
                'hospital': random.choice(HOSPITALS),
                'disease': disease,
                'last_test': TESTS_BY_DISEASE.get(disease, 'General Checkup'),
                'last_result': result,
                'risk': risk_tier,
                'care_gap': 'Open' if overdue > 0 else 'Closed',
                'age': age,
                'phone': phone,
                'channel': 'WhatsApp',
                'doctor': random.choice(DOCTORS),
                'overdue_days': overdue,
                'created_at': now.isoformat(),
            }
            new_patients.append(patient)
            self.stdout.write(
                f'  + {patient["patient_id"]}  {patient["name"]:25s}  '
                f'{disease:15s}  Risk: {risk_tier:8s}  Result: {result:10s}  '
                f'Overdue: {overdue:3d}d'
            )

        # Also generate one high-risk patient for the second phone number
        second_disease = random.choice(DISEASES)
        second_result = RESULTS_BY_DISEASE[second_disease]['High']
        second_patient = {
            'patient_id': f'P{next_num + count:05d}',
            'name': f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}',
            'hospital': random.choice(HOSPITALS),
            'disease': second_disease,
            'last_test': TESTS_BY_DISEASE.get(second_disease, 'General Checkup'),
            'last_result': second_result,
            'risk': 'High',
            'care_gap': 'Open',
            'age': random.randint(30, 65),
            'phone': SECOND_PHONE,
            'channel': 'WhatsApp',
            'doctor': random.choice(DOCTORS),
            'overdue_days': random.randint(60, 200),
            'created_at': now.isoformat(),
        }
        new_patients.append(second_patient)
        self.stdout.write(
            f'  + {second_patient["patient_id"]}  {second_patient["name"]:25s}  '
            f'{second_disease:15s}  Risk: High      Result: {second_result:10s}  '
            f'Overdue: {second_patient["overdue_days"]:3d}d  [SECOND PHONE]'
        )

        db.patients.insert_many(new_patients)
        self.stdout.write(self.style.SUCCESS(f'  ✓ {count + 1} patients added to database'))

        # ═══════════════════════════════════════════════════════════
        # STEP 2: Risk Analysis on new patients
        # ═══════════════════════════════════════════════════════════
        self.stdout.write(self.style.HTTP_INFO('\n── STEP 2: Running Risk Engine on new patients ──'))

        categorized = {'Critical': [], 'High': [], 'Medium': [], 'Low': []}

        for p in new_patients:
            risk = calculate_risk(p)
            score = calculate_risk_score(p)
            p['risk'] = risk
            p['risk_score'] = score

            db.patients.update_one(
                {'patient_id': p['patient_id']},
                {'$set': {'risk': risk, 'risk_score': score, 'risk_updated_at': now.isoformat()}}
            )

            gap = detect_care_gap(p)
            if gap:
                gap['risk'] = risk
                db.care_gaps.insert_one(gap)

            ai_decision = {
                'patient': p['name'],
                'patient_id': p['patient_id'],
                'hospital': p['hospital'],
                'risk': risk,
                'score': score,
                'action': _decide_action(risk, gap),
                'decided_at': now.isoformat(),
            }
            db.ai_decisions.insert_one(ai_decision)

            categorized[risk].append(p)
            self.stdout.write(
                f'  ⚡ {p["patient_id"]}  {p["name"]:25s}  '
                f'Risk: {risk:8s}  Score: {score:5.1f}  '
                f'Gap: {"YES" if gap else "NO"}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Risk analysis complete — '
            f'Critical:{len(categorized["Critical"])} '
            f'High:{len(categorized["High"])} '
            f'Medium:{len(categorized["Medium"])} '
            f'Low:{len(categorized["Low"])}'
        ))

        # ═══════════════════════════════════════════════════════════
        # STEP 3: Display Top 10 Highest-Risk Patients
        # ═══════════════════════════════════════════════════════════
        self.stdout.write(self.style.HTTP_INFO('\n── STEP 3: Top 10 Highest-Risk Patients ──'))

        # Sort all new patients by risk score descending
        all_sorted = sorted(new_patients, key=lambda x: x.get('risk_score', 0), reverse=True)
        top_10 = all_sorted[:10]

        self.stdout.write(
            f'\n  {"#":>3s}  {"Patient ID":<12s}  {"Name":<25s}  {"Disease":<15s}  '
            f'{"Risk":<10s}  {"Score":<7s}  {"Last Test":<12s}  {"Result":<10s}  '
            f'{"Overdue":<8s}  {"Hospital":<20s}'
        )
        self.stdout.write('  ' + '─' * 135)

        for idx, p in enumerate(top_10, 1):
            risk_label = p['risk']
            if risk_label == 'Critical':
                fmt = self.style.ERROR
            elif risk_label == 'High':
                fmt = self.style.WARNING
            else:
                fmt = self.style.SUCCESS

            self.stdout.write(
                f'  {idx:3d}  {p["patient_id"]:<12s}  {p["name"]:<25s}  {p.get("disease",""):<15s}  '
                f'{fmt(risk_label):<20s}  {p.get("risk_score",0):5.1f}   {p.get("last_test",""):<12s}  '
                f'{p.get("last_result",""):<10s}  {p.get("overdue_days",0):>4d}d    {p.get("hospital",""):<20s}'
            )

        self.stdout.write('')

        # ═══════════════════════════════════════════════════════════
        # STEP 4: Send WhatsApp to target patients
        #         English message + 3-option interactive menu
        # ═══════════════════════════════════════════════════════════
        self.stdout.write(self.style.HTTP_INFO(
            '\n── STEP 4: Sending WhatsApp to target patients ──'
        ))

        # Show daily message usage (Twilio free tier = 50/day)
        today_str = now.strftime('%Y-%m-%d')
        msgs_sent_today = db.messages.count_documents({
            'direction': 'outbound',
            'sent_at': {'$gte': today_str},
        })
        remaining = max(0, 50 - msgs_sent_today)
        self.stdout.write(f'  📊 Messages sent today: {msgs_sent_today}/50 (≈{remaining} remaining)')
        if remaining < 5 and not dry_run:
            self.stdout.write(self.style.WARNING(
                '  ⚠ Low message budget! Consider using --dry-run to avoid hitting the limit.'
            ))

        # Build list of patients to message: highest-risk + second phone patient
        targets = []
        if top_10:
            targets.append(top_10[0])
        # Add second-phone patient if not already in targets
        if second_patient.get('patient_id') not in [t.get('patient_id') for t in targets]:
            targets.append(second_patient)

        sent_count = 0
        failed_count = 0

        if not targets:
            self.stdout.write(self.style.WARNING('  ⚠ No patients to message'))

        for p in targets:
            patient_phone = p.get('phone', phone)
            tier = p['risk']

            # Build health alert message with 3-option interactive menu
            message_body = (
                f"🏥 *MediSynC Health Alert*\n\n"
                f"Dear {p['name']},\n\n"
                f"Your recent {p.get('last_test', 'test')} result ({p.get('last_result', 'N/A')}) "
                f"indicates that your {p.get('disease', 'condition')} requires attention.\n\n"
                f"Risk Level: *{tier}*\n\n"
                f"📋 Please reply with a number:\n"
                f"1️⃣ Book Appointment\n"
                f"2️⃣ Remind Me Later\n"
                f"3️⃣ Choose Language"
            )

            self.stdout.write(
                f'  🎯 Target: {p["patient_id"]} — {p["name"]} '
                f'(Risk: {tier}, Score: {p.get("risk_score", 0):.1f})'
            )
            self.stdout.write(f'  📱 Phone: {patient_phone}')

            # Clear any old whatsapp_state so patient enters main menu flow
            db.patients.update_one(
                {'patient_id': p['patient_id']},
                {'$set': {'whatsapp_state': ''}}
            )

            # Send via Twilio
            twilio_sid = ''
            delivery_status = 'Pending'

            if not dry_run:
                try:
                    from integrations.twilio_service import send_whatsapp_message
                    twilio_sid = send_whatsapp_message(patient_phone, message_body)
                    delivery_status = 'Delivered'
                    sent_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ SENT to {p["name"]} ({patient_phone}) '
                            f'[English + Language Menu] SID: {twilio_sid}'
                        )
                    )
                except Exception as e:
                    delivery_status = 'Failed'
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ FAILED {p["name"]}: {e}')
                    )
            else:
                delivery_status = 'Simulated'
                sent_count += 1
                self.stdout.write(
                    f'  📨 [DRY] {p["name"]} ({patient_phone}) [English + Language Menu]'
                )

            # Store message in DB
            db.messages.insert_one({
                'patient': p['name'],
                'patient_id': p['patient_id'],
                'hospital': p['hospital'],
                'channel': 'WhatsApp',
                'risk': tier,
                'message': message_body[:500],
                'language': 'English',
                'disease': p.get('disease', ''),
                'status': delivery_status,
                'twilio_sid': twilio_sid,
                'sent_at': now.isoformat(),
                'source': 'pipeline',
                'direction': 'outbound',
            })

        self.stdout.write(self.style.SUCCESS(
            f'\n  ✓ Messaging complete — Sent: {sent_count}  Failed: {failed_count}'
        ))

        # ═══════════════════════════════════════════════════════════
        # STEP 5: Log to activity feed and audit logs
        # ═══════════════════════════════════════════════════════════
        self.stdout.write(self.style.HTTP_INFO('\n── STEP 5: Updating activity feed & audit logs ──'))

        feed_time = now.strftime('%Y-%m-%d %H:%M')
        target_names = ', '.join(p['name'] for p in targets) if targets else 'N/A'
        target_risks = ', '.join(p['risk'] for p in targets) if targets else 'N/A'

        feed_entries = [
            {'scope': 'superadmin', 'icon': '🚀', 'text': f'Pipeline: {count + 1} new patients added and analyzed', 'time': feed_time, 'created_at': now},
            {'scope': 'superadmin', 'icon': '🤖', 'text': f'AI WhatsApp sent to {len(targets)} patients: {target_names}', 'time': feed_time, 'created_at': now},
            {'scope': 'hospital_admin', 'icon': '🔬', 'text': f'Pipeline processed {count + 1} new patients — Critical:{len(categorized["Critical"])} High:{len(categorized["High"])}', 'time': feed_time, 'created_at': now},
            {'scope': 'doctor', 'icon': '📋', 'text': f'{count + 1} new patients analyzed — Critical:{len(categorized["Critical"])} High:{len(categorized["High"])}', 'time': feed_time, 'created_at': now},
            {'scope': 'technician', 'icon': '📊', 'text': f'Pipeline: {count + 1} patients added — awaiting WhatsApp bookings', 'time': feed_time, 'created_at': now},
        ]
        db.activity_feed.insert_many(feed_entries)

        db.audit_logs.insert_one({
            'scope': 'superadmin',
            'user': 'SYSTEM',
            'action': f'Startup pipeline: {count + 1} patients added, WhatsApp sent to {target_names}',
            'hospital': 'ALL',
            'time': feed_time,
        })

        self.stdout.write(self.style.SUCCESS('  ✓ Activity feed and audit logs updated'))

        # ═══════════════════════════════════════════════════════════
        # SUMMARY
        # ═══════════════════════════════════════════════════════════
        self.stdout.write(self.style.WARNING(
            '\n'
            '╔══════════════════════════════════════════════════════════════╗\n'
            '║                 Pipeline Complete ✓                         ║\n'
            '╠══════════════════════════════════════════════════════════════╣\n'
            f'║  New Patients Added  : {count + 1:<5d}                                ║\n'
            f'║  Critical            : {len(categorized["Critical"]):<5d}                                ║\n'
            f'║  High                : {len(categorized["High"]):<5d}                                ║\n'
            f'║  Medium              : {len(categorized["Medium"]):<5d}                                ║\n'
            f'║  Low                 : {len(categorized["Low"]):<5d}                                ║\n'
            f'║  WhatsApp Sent To    : {sent_count} patients                              ║\n'
            f'║  Target Patients     : {target_names:<37s} ║\n'
            f'║  Bookings            : Via WhatsApp (patient-initiated)     ║\n'
            '╚══════════════════════════════════════════════════════════════╝\n'
        ))


def _decide_action(risk, gap):
    if not gap:
        return 'No action — tests up-to-date'
    if risk == 'Critical':
        return 'Immediate WhatsApp outreach + Home collection offer'
    if risk == 'High':
        return 'WhatsApp reminder — urgent follow-up needed'
    if risk == 'Medium':
        return 'WhatsApp reminder — routine check overdue'
    return 'WhatsApp reminder — gentle nudge for test'
