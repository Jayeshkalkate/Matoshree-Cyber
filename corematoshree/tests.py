from datetime import date, time, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import User, Service, ServiceCharge, Appointment, Application, ApplicationStatusHistory, DocumentUpload


class CoreWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='customer', password='StrongPassword123!', email='customer@example.test', phone='9876543210')
        self.admin = User.objects.create_user(username='admin', password='StrongPassword123!', email='admin@example.test', role='admin')
        self.service = Service.objects.create(name='Test Service', category='Digital', description='Test', payment_required=True)
        ServiceCharge.objects.create(service=self.service, charge=100)
        self.client = Client()

    def test_application_gets_tracking_number(self):
        app = Application.objects.create(user=self.user, service=self.service, full_name='Customer', phone='9876543210', email='customer@example.test', address='Test')
        self.assertTrue(app.application_number.startswith('MAT-'))
        self.assertEqual(Application.objects.filter(application_number=app.application_number).count(), 1)

    def test_public_service_page_is_available_without_login(self):
        response = self.client.get(reverse('services'))
        self.assertEqual(response.status_code, 200)

    def test_public_tracking_page_is_available_without_login(self):
        response = self.client.get(reverse('track_application'))
        self.assertEqual(response.status_code, 200)

    def test_appointment_slot_conflict_is_rejected_by_form(self):
        Appointment.objects.create(full_name='A', phone='9876543210', email='a@example.test', service=self.service, appointment_date=date.today() + timedelta(days=2), appointment_time=time(10, 0))
        response = self.client.post(reverse('appointment'), {
            'full_name': 'B', 'phone': '9876543211', 'email': 'b@example.test', 'service': self.service.id,
            'appointment_date': (date.today() + timedelta(days=2)).isoformat(), 'appointment_time': '10:00', 'message': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Appointment.objects.filter(appointment_time=time(10, 0)).count(), 1)

    def test_application_status_history_can_be_recorded(self):
        app = Application.objects.create(user=self.user, service=self.service, full_name='Customer', phone='9876543210', email='customer@example.test', address='Test')
        event = ApplicationStatusHistory.objects.create(application=app, old_status='', new_status='pending', changed_by=self.admin, note='Submitted')
        self.assertEqual(event.new_status, 'pending')

    def test_document_download_requires_owner_or_admin(self):
        app = Application.objects.create(user=self.user, service=self.service, full_name='Customer', phone='9876543210', email='customer@example.test', address='Test')
        doc = DocumentUpload.objects.create(application=app, document_name='Test', file=SimpleUploadedFile('test.pdf', b'%PDF-1.4 test'))
        response = self.client.get(reverse('document_download', kwargs={'doc_id': doc.id}))
        self.assertEqual(response.status_code, 302)  # unauthenticated -> login
