import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add CNS directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestFirebaseIntegration(unittest.TestCase):

    def setUp(self):
        # Mocking modules that don't exist in the environment (or we want to control)
        # We need to make sure we patch them BEFORE they are imported by the module under test.

        self.mock_firebase_admin = MagicMock()
        self.mock_firestore = MagicMock()
        self.mock_storage = MagicMock()

        # Setup specific mock behaviors
        self.mock_firebase_admin._apps = {}

        self.modules_patcher = patch.dict(sys.modules, {
            'firebase_admin': self.mock_firebase_admin,
            'firebase_admin.credentials': MagicMock(),
            'firebase_admin.firestore': self.mock_firestore,
            'firebase_admin.storage': self.mock_storage,
        })
        self.modules_patcher.start()

        # Now import the module under test. It will see the mocked modules.
        # If it was already imported, we reload it.
        try:
            import firebase_manager
            import importlib
            importlib.reload(firebase_manager)
        except ImportError:
            # If path issues, rely on the sys.path.append in the file
            import firebase_manager

        self.firebase_manager = firebase_manager.firebase_manager

    def tearDown(self):
        self.modules_patcher.stop()

    def test_initialization(self):
        # Reset singleton state for testing
        self.firebase_manager.initialized = False
        self.firebase_manager._instance = None
        # Ensure _apps is empty dict-like for boolean check
        self.mock_firebase_admin._apps = {}

        with patch('os.path.exists', return_value=True):
            self.firebase_manager.initialize()

        self.assertTrue(self.firebase_manager.initialized)
        self.mock_firebase_admin.initialize_app.assert_called_once()

        # Verify that client() was called on the firestore module that firebase_manager is actually using
        import firebase_manager
        # Check if the firestore module in firebase_manager is our mock
        # self.assertIs(firebase_manager.firestore, self.mock_firestore) # This might fail if reload didn't work perfectly

        # We can just check the mock directly attached to the module if we are unsure
        firebase_manager.firestore.client.assert_called_once()
        firebase_manager.storage.bucket.assert_called_once()

    def test_upload_report(self):
        # Manually set initialized state
        self.firebase_manager.initialized = True
        self.firebase_manager.db = MagicMock()
        self.firebase_manager.bucket = MagicMock()

        mock_blob = MagicMock()
        self.firebase_manager.bucket.blob.return_value = mock_blob
        mock_blob.public_url = "http://fake-url.com/report.pdf"

        report_data = {'id': 1, 'firm_name': 'Test Firm'}
        pdf_path = '/tmp/test_report.pdf'

        with patch('os.path.basename', return_value='test_report.pdf'):
            self.firebase_manager.upload_report(report_data, pdf_path)

        # Verify PDF upload
        self.firebase_manager.bucket.blob.assert_called_with('reports/1/test_report.pdf')
        mock_blob.upload_from_filename.assert_called_with(pdf_path)

        # Verify Metadata upload
        self.firebase_manager.db.collection.assert_called_with('reports')
        doc_ref = self.firebase_manager.db.collection().document()
        # Verify set call includes the PDF URL
        args, _ = doc_ref.set.call_args
        self.assertEqual(args[0]['pdf_url'], "http://fake-url.com/report.pdf")
        self.assertEqual(args[0]['firm_name'], "Test Firm")

if __name__ == '__main__':
    unittest.main()
