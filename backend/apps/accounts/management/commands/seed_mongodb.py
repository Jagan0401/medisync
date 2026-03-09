"""
Management command to seed MongoDB with all application data.
Replaces all hardcoded template data with database records.
"""

from django.core.management.base import BaseCommand

from config.db import db


class Command(BaseCommand):
    help = 'Seed MongoDB with initial application data'

    def handle(self, *args, **options):
        self.stdout.write('Dropping existing collections...')
        for name in [
            'hospitals', 'platform_users', 'patients', 'care_gaps', 'messages',
            'bookings', 'ai_decisions', 'activity_feed', 'system_services',
            'error_logs', 'subscriptions', 'protocols', 'audit_logs',
            'dataset_uploads', 'doctors', 'technicians',
            'appointments', 'test_results', 'followups', 'analytics',
        ]:
            db[name].drop()

        self._seed_hospitals()
        self._seed_platform_users()
        self._seed_patients()
        self._seed_care_gaps()
        self._seed_messages()
        self._seed_bookings()
        self._seed_ai_decisions()
        self._seed_activity_feed()
        self._seed_system_services()
        self._seed_error_logs()
        self._seed_subscriptions()
        self._seed_protocols()
        self._seed_audit_logs()
        self._seed_dataset_uploads()
        self._seed_doctors()
        self._seed_technicians()
        self._seed_appointments()
        self._seed_test_results()
        self._seed_followups()
        self._seed_analytics()

        self.stdout.write(self.style.SUCCESS('MongoDB seeded successfully!'))

    # ── Hospitals / Tenants ──────────────────────────────────────────
    def _seed_hospitals(self):
        db.hospitals.insert_many([
            {'name': 'Apollo Chennai', 'tenant_id': 'apollo_ch', 'plan': 'Enterprise', 'patients': 35200, 'doctors_count': 120, 'status': 'Active', 'is_active': True},
            {'name': 'Fortis Bangalore', 'tenant_id': 'fortis_blr', 'plan': 'Pro', 'patients': 21500, 'doctors_count': 82, 'status': 'Active', 'is_active': True},
            {'name': 'GlobalCare Delhi', 'tenant_id': 'global_del', 'plan': 'Starter', 'patients': 4800, 'doctors_count': 25, 'status': 'Active', 'is_active': True},
            {'name': 'MedLife Hyderabad', 'tenant_id': 'medlife_hyd', 'plan': 'Pro', 'patients': 17200, 'doctors_count': 60, 'status': 'Suspended', 'is_active': False},
            {'name': 'HealthFirst Pune', 'tenant_id': 'health_pune', 'plan': 'Starter', 'patients': 3900, 'doctors_count': 18, 'status': 'Active', 'is_active': True},
        ])
        self.stdout.write('  ✓ hospitals')

    # ── Platform Users ───────────────────────────────────────────────
    def _seed_platform_users(self):
        db.platform_users.insert_many([
            {'name': 'Dr. Meera Iyer', 'role': 'Hospital Admin', 'hospital': 'Apollo Chennai', 'status': 'Active', 'last_login': 'Today'},
            {'name': 'Dr. Rahul Sharma', 'role': 'Doctor', 'hospital': 'Fortis Bangalore', 'status': 'Active', 'last_login': 'Today'},
            {'name': 'Arjun Patel', 'role': 'Lab Technician', 'hospital': 'GlobalCare Delhi', 'status': 'Active', 'last_login': 'Today'},
            {'name': 'Amit Verma', 'role': 'Platform Admin', 'hospital': 'MediSynC', 'status': 'Active', 'last_login': 'Today'},
        ])
        self.stdout.write('  ✓ platform_users')

    # ── Patients ─────────────────────────────────────────────────────
    def _seed_patients(self):
        db.patients.insert_many([
            {'patient_id': 'P1001', 'name': 'Ravi Kumar', 'hospital': 'Apollo Chennai', 'disease': 'Diabetes', 'last_test': '120 days ago', 'risk': 'High', 'care_gap': 'Open', 'age': 52, 'phone': '+91 98765 43210', 'channel': 'WhatsApp', 'doctor': 'Dr. Rahul'},
            {'patient_id': 'P1002', 'name': 'Meena Iyer', 'hospital': 'Fortis Bangalore', 'disease': 'CKD', 'last_test': '200 days ago', 'risk': 'Critical', 'care_gap': 'Open', 'age': 45, 'phone': '+91 98765 43211', 'channel': 'WhatsApp', 'doctor': 'Dr. Meera'},
            {'patient_id': 'P1003', 'name': 'Arjun Patel', 'hospital': 'GlobalCare Delhi', 'disease': 'Hypertension', 'last_test': '60 days ago', 'risk': 'Medium', 'care_gap': 'Closed', 'age': 38, 'phone': '+91 98765 43212', 'channel': 'SMS', 'doctor': 'Dr. Arjun'},
            {'patient_id': 'P1004', 'name': 'Neha Sharma', 'hospital': 'MedLife Hyderabad', 'disease': 'Diabetes', 'last_test': '30 days ago', 'risk': 'Low', 'care_gap': 'Closed', 'age': 60, 'phone': '+91 98765 43213', 'channel': 'WhatsApp', 'doctor': 'Dr. Rahul'},
            {'patient_id': 'P1005', 'name': 'Karthik Rao', 'hospital': 'HealthFirst Pune', 'disease': 'Hypothyroidism', 'last_test': '150 days ago', 'risk': 'High', 'care_gap': 'Open', 'age': 55, 'phone': '+91 98765 43214', 'channel': 'WhatsApp', 'doctor': 'Dr. Kavita'},
        ])
        self.stdout.write('  ✓ patients')

    # ── Care Gaps ────────────────────────────────────────────────────
    def _seed_care_gaps(self):
        db.care_gaps.insert_many([
            {'patient': 'Ravi Kumar', 'test': 'HbA1c', 'overdue_days': 120, 'risk': 'High', 'status': 'Open'},
            {'patient': 'Meena Iyer', 'test': 'Creatinine', 'overdue_days': 200, 'risk': 'Critical', 'status': 'Open'},
            {'patient': 'Arjun Patel', 'test': 'BP Check', 'overdue_days': 95, 'risk': 'Medium', 'status': 'Open'},
            {'patient': 'Neha Sharma', 'test': 'HbA1c', 'overdue_days': 30, 'risk': 'Low', 'status': 'Closed'},
            {'patient': 'Karthik Rao', 'test': 'TSH', 'overdue_days': 150, 'risk': 'High', 'status': 'Open'},
        ])
        self.stdout.write('  ✓ care_gaps')

    # ── Messages ─────────────────────────────────────────────────────
    def _seed_messages(self):
        db.messages.insert_many([
            {'patient': 'Ravi Kumar', 'hospital': 'Apollo', 'channel': 'WhatsApp', 'message': 'HbA1c reminder', 'disease': 'Diabetes', 'status': 'Delivered', 'sent_at': 'Mar 07'},
            {'patient': 'Meena Iyer', 'hospital': 'Fortis', 'channel': 'WhatsApp', 'message': 'Creatinine alert', 'disease': 'CKD', 'status': 'Replied', 'sent_at': 'Mar 08'},
            {'patient': 'Arjun Patel', 'hospital': 'GlobalCare', 'channel': 'SMS', 'message': 'BP reminder', 'disease': 'Hypertension', 'status': 'Sent', 'sent_at': 'Mar 08'},
            {'patient': 'Neha Sharma', 'hospital': 'MedLife', 'channel': 'WhatsApp', 'message': 'HbA1c reminder', 'disease': 'Diabetes', 'status': 'Delivered', 'sent_at': 'Mar 09'},
            {'patient': 'Karthik Rao', 'hospital': 'Apollo', 'channel': 'WhatsApp', 'message': 'Kidney test reminder', 'disease': 'CKD', 'status': 'Failed', 'sent_at': 'Mar 09'},
        ])
        self.stdout.write('  ✓ messages')

    # ── Bookings ─────────────────────────────────────────────────────
    def _seed_bookings(self):
        db.bookings.insert_many([
            {'patient': 'Ravi Kumar', 'test': 'HbA1c', 'technician': 'Arjun Patel', 'date': 'Mar 12', 'status': 'Scheduled'},
            {'patient': 'Meena Iyer', 'test': 'Creatinine', 'technician': 'Rahul Singh', 'date': 'Mar 11', 'status': 'Completed'},
            {'patient': 'Arjun Patel', 'test': 'BP Test', 'technician': 'Kavya Nair', 'date': 'Mar 10', 'status': 'Completed'},
            {'patient': 'Neha Sharma', 'test': 'TSH', 'technician': 'Ankit Kumar', 'date': 'Mar 14', 'status': 'Scheduled'},
            {'patient': 'Karthik Rao', 'test': 'Creatinine', 'technician': 'Arjun Patel', 'date': 'Mar 13', 'status': 'Scheduled'},
        ])
        self.stdout.write('  ✓ bookings')

    # ── AI Decisions ─────────────────────────────────────────────────
    def _seed_ai_decisions(self):
        db.ai_decisions.insert_many([
            {'patient': 'Ravi Kumar', 'hospital': 'Apollo', 'risk': 'High', 'action': 'Send HbA1c reminder'},
            {'patient': 'Meena Iyer', 'hospital': 'Fortis', 'risk': 'Critical', 'action': 'Escalate to doctor'},
            {'patient': 'Arjun Patel', 'hospital': 'GlobalCare', 'risk': 'Medium', 'action': 'Send BP reminder'},
            {'patient': 'Neha Sharma', 'hospital': 'MedLife', 'risk': 'Low', 'action': 'No action required'},
            {'patient': 'Karthik Rao', 'hospital': 'Apollo', 'risk': 'High', 'action': 'Send creatinine reminder'},
        ])
        self.stdout.write('  ✓ ai_decisions')

    # ── Activity Feed ────────────────────────────────────────────────
    def _seed_activity_feed(self):
        db.activity_feed.insert_many([
            # Superadmin feed
            {'scope': 'superadmin', 'icon': '📂', 'text': 'Apollo Chennai uploaded 20,000 patient records', 'time': '2 mins ago'},
            {'scope': 'superadmin', 'icon': '🤖', 'text': 'AI sent 1,120 automated outreach messages', 'time': '12 mins ago'},
            {'scope': 'superadmin', 'icon': '✅', 'text': 'Fortis Bangalore closed 48 care gaps', 'time': '45 mins ago'},
            {'scope': 'superadmin', 'icon': '⚠️', 'text': 'Doctor escalated critical CKD patient in GlobalCare', 'time': '2 hours ago'},
            # Doctor feed
            {'scope': 'doctor', 'icon': '🤖', 'text': 'AI detected overdue HbA1c for Ravi Kumar', 'time': '2 mins ago'},
            {'scope': 'doctor', 'icon': '📋', 'text': 'Patient Meena Iyer booked creatinine test', 'time': '15 mins ago'},
            {'scope': 'doctor', 'icon': '🧪', 'text': 'Lab reported new test results for Arjun Patel', 'time': '1 hour ago'},
            {'scope': 'doctor', 'icon': '⚠️', 'text': 'Critical CKD patient escalated to doctor inbox', 'time': '4 hours ago'},
            # Technician feed
            {'scope': 'technician', 'icon': '🧪', 'text': 'Lab technician assigned to CKD patient #P1002', 'time': '1 hour ago'},
            {'scope': 'technician', 'icon': '🏠', 'text': 'Home sample collection completed for Ravi Kumar', 'time': '2 hours ago'},
            {'scope': 'technician', 'icon': '📅', 'text': 'New booking scheduled for Neha Sharma', 'time': '4 hours ago'},
            # Hospital admin feed
            {'scope': 'hospital_admin', 'icon': '📂', 'text': 'New dataset uploaded (20,000 records)', 'time': '5 mins ago'},
            {'scope': 'hospital_admin', 'icon': '🤖', 'text': 'AI engine processed 350 care gaps', 'time': '15 mins ago'},
            {'scope': 'hospital_admin', 'icon': '✅', 'text': '24 care gaps resolved today', 'time': '1 hour ago'},
            {'scope': 'hospital_admin', 'icon': '🏠', 'text': 'Home collection booked for Ravi Kumar', 'time': '2 hours ago'},
            {'scope': 'hospital_admin', 'icon': '⚠️', 'text': 'Critical patient escalation: Meena Iyer', 'time': '3 hours ago'},
        ])
        self.stdout.write('  ✓ activity_feed')

    # ── System Services ──────────────────────────────────────────────
    def _seed_system_services(self):
        db.system_services.insert_many([
            {'service': 'Django Backend', 'status': 'Online', 'response_time': '120 ms'},
            {'service': 'MongoDB', 'status': 'Healthy', 'response_time': '80 ms'},
            {'service': 'AI Engine', 'status': 'Online', 'response_time': '310 ms'},
            {'service': 'Twilio API', 'status': 'Connected', 'response_time': '150 ms'},
            {'service': 'Scheduler', 'status': 'Running', 'response_time': '90 ms'},
        ])
        self.stdout.write('  ✓ system_services')

    # ── Error Logs ───────────────────────────────────────────────────
    def _seed_error_logs(self):
        db.error_logs.insert_many([
            {'error': 'Database Timeout', 'module': 'API', 'timestamp': 'Today', 'status': 'Resolved'},
            {'error': 'Twilio Failure', 'module': 'Messaging', 'timestamp': 'Today', 'status': 'Pending'},
            {'error': 'AI Engine Timeout', 'module': 'Risk Engine', 'timestamp': 'Yesterday', 'status': 'Resolved'},
            {'error': 'Webhook Delay', 'module': 'Messaging', 'timestamp': 'Yesterday', 'status': 'Resolved'},
            {'error': 'Cache Error', 'module': 'API', 'timestamp': 'Today', 'status': 'Pending'},
        ])
        self.stdout.write('  ✓ error_logs')

    # ── Subscriptions / Billing ──────────────────────────────────────
    def _seed_subscriptions(self):
        db.subscriptions.insert_many([
            {'hospital': 'Apollo Chennai', 'plan': 'Enterprise', 'limit': 'Unlimited', 'status': 'Active'},
            {'hospital': 'Fortis Bangalore', 'plan': 'Pro', 'limit': '50,000', 'status': 'Active'},
            {'hospital': 'GlobalCare Delhi', 'plan': 'Starter', 'limit': '5,000', 'status': 'Active'},
            {'hospital': 'MedLife Hyderabad', 'plan': 'Pro', 'limit': '50,000', 'status': 'Suspended'},
            {'hospital': 'HealthFirst Pune', 'plan': 'Starter', 'limit': '5,000', 'status': 'Active'},
        ])
        self.stdout.write('  ✓ subscriptions')

    # ── Protocols ────────────────────────────────────────────────────
    def _seed_protocols(self):
        db.protocols.insert_many([
            {'disease': 'Diabetes', 'test': 'HbA1c', 'frequency': '90 days'},
            {'disease': 'CKD', 'test': 'Creatinine', 'frequency': '180 days'},
            {'disease': 'Hypothyroidism', 'test': 'TSH', 'frequency': '180 days'},
            {'disease': 'Hypertension', 'test': 'BP Check', 'frequency': '90 days'},
            {'disease': 'Diabetes', 'test': 'Kidney Panel', 'frequency': '180 days'},
        ])
        self.stdout.write('  ✓ protocols')

    # ── Audit Logs ───────────────────────────────────────────────────
    def _seed_audit_logs(self):
        db.audit_logs.insert_many([
            # Superadmin
            {'scope': 'superadmin', 'user': 'SuperAdmin', 'action': 'Created tenant Apollo', 'hospital': 'MediSynC', 'time': 'Today'},
            {'scope': 'superadmin', 'user': 'Dr. Meera Iyer', 'action': 'Escalated patient Ravi', 'hospital': 'Apollo', 'time': 'Today'},
            {'scope': 'superadmin', 'user': 'Kavya Nair', 'action': 'Booked home test', 'hospital': 'Apollo', 'time': 'Today'},
            {'scope': 'superadmin', 'user': 'System AI', 'action': 'Sent outreach messages', 'hospital': 'GlobalCare', 'time': 'Today'},
            {'scope': 'superadmin', 'user': 'Admin Rahul', 'action': 'Updated hospital plan', 'hospital': 'Fortis', 'time': 'Yesterday'},
            # Hospital admin
            {'scope': 'hospital_admin', 'user': 'Admin', 'action': 'Added doctor Dr. Rahul Sharma', 'time': 'Today'},
            {'scope': 'hospital_admin', 'user': 'Technician', 'action': 'Booked home test #B4920', 'time': 'Today'},
            {'scope': 'hospital_admin', 'user': 'Doctor', 'action': 'Escalated CKD patient #P1002', 'time': 'Today'},
            {'scope': 'hospital_admin', 'user': 'AI Engine', 'action': 'Sent 320 automated reminders', 'time': 'Today'},
            {'scope': 'hospital_admin', 'user': 'Admin', 'action': 'Uploaded dataset (Apollo_Mar_09.csv)', 'time': 'Yesterday'},
            # Doctor
            {'scope': 'doctor', 'icon': '👤', 'action': 'Sent reminder to Ravi Kumar', 'time': 'Today, 10:45 AM'},
            {'scope': 'doctor', 'icon': '📝', 'action': 'Reviewed CKD report #RK920', 'time': 'Today, 09:12 AM'},
            {'scope': 'doctor', 'icon': '⚠️', 'action': 'Escalated patient Meena Iyer', 'time': 'Today, 08:30 AM'},
            {'scope': 'doctor', 'icon': '📅', 'action': 'Scheduled follow-up with Arjun Patel', 'time': 'Yesterday'},
            {'scope': 'doctor', 'icon': '🤖', 'action': 'System AI generated patient alert', 'time': 'Yesterday'},
            # Technician
            {'scope': 'technician', 'action': 'Completed sample collection', 'target': 'Ravi Kumar', 'time': 'Today, 11:45 AM'},
            {'scope': 'technician', 'action': 'Processed HbA1c test', 'target': 'Meena Iyer', 'time': 'Today, 10:20 AM'},
            {'scope': 'technician', 'action': 'Updated booking status', 'target': '#BK9204', 'time': 'Yesterday'},
        ])
        self.stdout.write('  ✓ audit_logs')

    # ── Dataset Uploads ──────────────────────────────────────────────
    def _seed_dataset_uploads(self):
        db.dataset_uploads.insert_many([
            {'hospital': 'Apollo Chennai', 'file': 'patients_apollo.csv', 'records': '20,000', 'date': 'Mar 10', 'status': 'Completed'},
            {'hospital': 'Fortis Bangalore', 'file': 'dataset_fortis.csv', 'records': '15,000', 'date': 'Mar 9', 'status': 'Completed'},
            {'hospital': 'GlobalCare Delhi', 'file': 'patients_delhi.csv', 'records': '5,000', 'date': 'Mar 8', 'status': 'Completed'},
            {'hospital': 'MedLife Hyderabad', 'file': 'dataset_hyd.csv', 'records': '10,000', 'date': 'Mar 7', 'status': 'Completed'},
            {'hospital': 'HealthFirst Pune', 'file': 'dataset_pune.csv', 'records': '4,000', 'date': 'Mar 6', 'status': 'Completed'},
        ])
        self.stdout.write('  ✓ dataset_uploads')

    # ── Doctors ──────────────────────────────────────────────────────
    def _seed_doctors(self):
        db.doctors.insert_many([
            {'name': 'Dr. Rahul Sharma', 'specialty': 'Endocrinology', 'patients': 420, 'status': 'Active'},
            {'name': 'Dr. Meera Iyer', 'specialty': 'Nephrology', 'patients': 280, 'status': 'Active'},
            {'name': 'Dr. Arjun Singh', 'specialty': 'Cardiology', 'patients': 310, 'status': 'Active'},
            {'name': 'Dr. Kavita Rao', 'specialty': 'Internal Med', 'patients': 190, 'status': 'Active'},
            {'name': 'Dr. Amit Verma', 'specialty': 'Endocrinology', 'patients': 260, 'status': 'Active'},
        ])
        self.stdout.write('  ✓ doctors')

    # ── Technicians ──────────────────────────────────────────────────
    def _seed_technicians(self):
        db.technicians.insert_many([
            {'name': 'Arjun Patel', 'area': 'South Zone', 'jobs': 12, 'status': 'Active'},
            {'name': 'Rahul Singh', 'area': 'North Zone', 'jobs': 10, 'status': 'Active'},
            {'name': 'Ankit Kumar', 'area': 'East Zone', 'jobs': 8, 'status': 'Active'},
            {'name': 'Vikas Jain', 'area': 'West Zone', 'jobs': 6, 'status': 'Active'},
            {'name': 'Rohit Sinha', 'area': 'Central Zone', 'jobs': 5, 'status': 'Active'},
        ])
        self.stdout.write('  ✓ technicians')

    # ── Appointments ─────────────────────────────────────────────────
    def _seed_appointments(self):
        db.appointments.insert_many([
            {'patient': 'Ravi Kumar', 'purpose': 'HbA1c follow-up', 'date': 'Mar 20', 'status': 'Scheduled'},
            {'patient': 'Meena Iyer', 'purpose': 'CKD review', 'date': 'Mar 18', 'status': 'Scheduled'},
            {'patient': 'Arjun Patel', 'purpose': 'BP monitoring', 'date': 'Mar 17', 'status': 'Completed'},
            {'patient': 'Neha Sharma', 'purpose': 'Diabetes review', 'date': 'Mar 25', 'status': 'Scheduled'},
            {'patient': 'Karthik Rao', 'purpose': 'Thyroid review', 'date': 'Mar 22', 'status': 'Scheduled'},
        ])
        self.stdout.write('  ✓ appointments')

    # ── Test Results ─────────────────────────────────────────────────
    def _seed_test_results(self):
        db.test_results.insert_many([
            {'patient': 'Ravi Kumar', 'test': 'HbA1c', 'result': '9.5%', 'date': 'Jan 10', 'notes': 'Hyperglycemic', 'status': 'Delivered'},
            {'patient': 'Ravi Kumar', 'test': 'Creatinine', 'result': '1.8', 'date': 'Feb 3', 'notes': 'Check Kidney', 'status': 'Delivered'},
            {'patient': 'Ravi Kumar', 'test': 'BP Check', 'result': '145/92', 'date': 'Mar 1', 'notes': 'Elevated', 'status': 'Delivered'},
            {'patient': 'Ravi Kumar', 'test': 'TSH', 'result': '5.2', 'date': 'Feb 12', 'notes': 'Normal Range', 'status': 'Delivered'},
            {'patient': 'Ravi Kumar', 'test': 'Lipid Profile', 'result': '210', 'date': 'Dec 18', 'notes': 'Borderline', 'status': 'Delivered'},
            # Recent lab reports (all patients)
            {'patient': 'Ravi Kumar', 'test': 'HbA1c', 'result': '9.5', 'date': 'Mar 10', 'notes': '', 'scope': 'recent', 'status': 'Collected'},
            {'patient': 'Meena Iyer', 'test': 'Creatinine', 'result': '2.1', 'date': 'Mar 9', 'notes': '', 'scope': 'recent', 'status': 'In Transit'},
            {'patient': 'Arjun Patel', 'test': 'BP Check', 'result': '145/92', 'date': 'Mar 8', 'notes': '', 'scope': 'recent', 'status': 'Delivered'},
            {'patient': 'Neha Sharma', 'test': 'HbA1c', 'result': '6.8', 'date': 'Mar 7', 'notes': '', 'scope': 'recent', 'status': 'Collected'},
            {'patient': 'Karthik Rao', 'test': 'TSH', 'result': '5.3', 'date': 'Mar 6', 'notes': '', 'scope': 'recent', 'status': 'Delivered'},
        ])
        self.stdout.write('  ✓ test_results')

    # ── Follow-ups ───────────────────────────────────────────────────
    def _seed_followups(self):
        db.followups.insert_many([
            {'patient': 'Ravi Kumar', 'task': 'Confirm HbA1c booking', 'due_date': 'Mar 15', 'status': 'Pending'},
            {'patient': 'Meena Iyer', 'task': 'CKD monitoring call', 'due_date': 'Mar 16', 'status': 'Pending'},
            {'patient': 'Arjun Patel', 'task': 'BP test reminder', 'due_date': 'Mar 14', 'status': 'Completed'},
            {'patient': 'Neha Sharma', 'task': 'Diabetes review', 'due_date': 'Mar 18', 'status': 'Pending'},
            {'patient': 'Karthik Rao', 'task': 'Thyroid follow-up', 'due_date': 'Mar 17', 'status': 'Pending'},
        ])
        self.stdout.write('  ✓ followups')

    # ── Analytics ────────────────────────────────────────────────────
    def _seed_analytics(self):
        db.analytics.insert_many([
            # Superadmin analytics
            {'scope': 'superadmin', 'label': 'Diabetes', 'value': '45%'},
            {'scope': 'superadmin', 'label': 'Hypertension', 'value': '30%'},
            {'scope': 'superadmin', 'label': 'CKD', 'value': '15%'},
            {'scope': 'superadmin', 'label': 'Critical Tier', 'value': '10%'},
            {'scope': 'superadmin', 'conversion_rate': '38%'},
            # Hospital admin analytics
            {'scope': 'hospital_admin', 'label': 'Outreach Success', 'value': '62%'},
            {'scope': 'hospital_admin', 'label': 'Gap Closure', 'value': '38%'},
            {'scope': 'hospital_admin', 'label': 'Patient Retention', 'value': '94%'},
            # Doctor analytics
            {'scope': 'doctor', 'label': 'Response Rate', 'value': '84%'},
            {'scope': 'doctor', 'label': 'Care Closure', 'value': '62%'},
            {'scope': 'doctor', 'label': 'Patient NPS', 'value': '9.2'},
        ])
        self.stdout.write('  ✓ analytics')
