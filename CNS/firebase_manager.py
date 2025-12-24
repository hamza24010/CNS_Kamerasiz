import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import datetime

class FirebaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def initialize(self):
        if self.initialized:
            return

        try:
            # Check if service account file exists
            key_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
            if not os.path.exists(key_path):
                print(f"Warning: Firebase serviceAccountKey.json not found at {key_path}. Firebase integration disabled.")
                return

            cred = credentials.Certificate(key_path)
            # Check if already initialized to avoid ValueError
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred, {
                    'storageBucket': 'dummy-project-id.appspot.com' # Placeholder, user needs to update
                })

            self.db = firestore.client()
            self.bucket = storage.bucket()
            self.initialized = True
            print("Firebase initialized successfully.")
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
            self.initialized = False

    def upload_report(self, report_metadata, pdf_path):
        """
        Uploads report metadata to Firestore and PDF to Storage.
        report_metadata: dict containing report details (id, firm_name, date, etc.)
        pdf_path: local path to the generated PDF
        """
        if not self.initialized:
            self.initialize()
            if not self.initialized:
                print("Firebase not initialized. Skipping upload.")
                return

        try:
            report_id = str(report_metadata.get('id', 'unknown'))

            # 1. Upload PDF to Storage
            blob_name = f"reports/{report_id}/{os.path.basename(pdf_path)}"
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(pdf_path)

            # Make the blob publicly accessible (or generate a signed URL)
            # For simplicity in this demo, we make it public (be careful in prod)
            blob.make_public()
            pdf_url = blob.public_url

            # 2. Upload Metadata to Firestore
            doc_ref = self.db.collection('reports').document(report_id)

            data = report_metadata.copy()
            data['pdf_url'] = pdf_url
            data['uploaded_at'] = datetime.datetime.now()

            doc_ref.set(data)
            print(f"Report {report_id} uploaded successfully to Firebase.")

        except Exception as e:
            print(f"Error uploading report to Firebase: {e}")

# Global instance
firebase_manager = FirebaseManager()
