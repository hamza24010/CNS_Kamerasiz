import unittest
from unittest.mock import MagicMock, patch, ANY
import sys

# --- Mocking dependencies ---
sys.modules['settings'] = MagicMock()
sys.modules['video'] = MagicMock()
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['PyQt5'] = MagicMock()
sys.modules['PyQt5.QtWidgets'] = MagicMock()
sys.modules['PyQt5.QtCore'] = MagicMock()
sys.modules['PyQt5.QtGui'] = MagicMock()
sys.modules['matplotlib.backends.backend_qt5agg'] = MagicMock()

# Mock reportlab and matplotlib before importing mainS
# Note: Since mainS imports specific classes, we need to ensure they are mocked when mainS is imported.
# But mainS might already be imported by other tests.
# We will rely on patching mainS attributes in setUp or tests.
sys.modules['reportlab'] = MagicMock()
sys.modules['reportlab.platypus'] = MagicMock()
sys.modules['reportlab.lib.pagesizes'] = MagicMock()
sys.modules['reportlab.lib'] = MagicMock()
sys.modules['reportlab.lib.styles'] = MagicMock()
sys.modules['reportlab.pdfbase'] = MagicMock()
sys.modules['reportlab.pdfbase.ttfonts'] = MagicMock()
sys.modules['matplotlib.pyplot'] = MagicMock()
sys.modules['matplotlib.figure'] = MagicMock()

import CNS.mainS as mainS

class TestPdfExport(unittest.TestCase):

    def setUp(self):
        # Force critical classes to be Mocks to avoid Font/File I/O errors
        mainS.Paragraph = MagicMock()
        mainS.SimpleDocTemplate = MagicMock()
        mainS.Table = MagicMock()
        mainS.Image = MagicMock()

        self.ops = mainS.ReportDetailOperations()
        self.ops.ui = MagicMock()

    @patch('CNS.mainS.get_parti')
    @patch('CNS.mainS.get_report_details')
    @patch('CNS.mainS.MatplotlibDialog') # Mock graph generation
    def test_export_pdf_creation(self, mock_graph_dialog, mock_get_details, mock_get_parti):
        # Setup data
        mock_get_parti.return_value = [
            (1, "Start", "End", "Type", "100", "50", "Info")
        ]
        mock_get_details.return_value = [
            ["50"]*15 + ["Step", "Time"],
            ["55"]*15 + ["Step", "Time"]
        ]

        # Mock Graph saving
        mock_graph_instance = mock_graph_dialog.return_value
        mock_graph_instance.save_filtered_graph_png.return_value = "dummy_graph.png"

        # Call export
        mainS.settings.VALITADITON = False
        mainS.settings.DESIRED_TEMP = 56
        mainS.settings.FIRM_NAME = "TestFirm"
        mainS.settings.OVEN_NO = "1"
        mainS.settings.PRINTER_NAME = "PDF"

        # Call the method
        with patch.object(self.ops, 'get_desktop_path', return_value="/tmp"):
             self.ops.export_munite_pdf(1, oto=False)

        # Verification
        # Check if SimpleDocTemplate was instantiated with a PDF file
        self.assertTrue(mainS.SimpleDocTemplate.called)
        args, _ = mainS.SimpleDocTemplate.call_args
        filename = args[0]
        self.assertTrue(filename.endswith(".pdf"))

        # Check if build was called
        doc_instance = mainS.SimpleDocTemplate.return_value
        self.assertTrue(doc_instance.build.called)

    @patch('CNS.mainS.get_parti')
    @patch('CNS.mainS.get_report_details')
    @patch('CNS.mainS.MatplotlibDialog')
    def test_export_colored_pdf(self, mock_graph_dialog, mock_get_details, mock_get_parti):
        # Similar setup for the other export function
        mock_get_parti.return_value = [(1, "Start", "End", "Type", "100", "50", "Info")]
        mock_get_details.return_value = [["50"]*15 + ["Step", "Time"]]
        mock_graph_instance = mock_graph_dialog.return_value
        mock_graph_instance.save_filtered_graph_png.return_value = None

        mainS.settings.VALITADITON = False

        with patch.object(self.ops, 'get_desktop_path', return_value="/tmp"):
             self.ops.export_to_pdf_colored(1, oto=False)

        self.assertTrue(mainS.SimpleDocTemplate.called)
        doc_instance = mainS.SimpleDocTemplate.return_value
        self.assertTrue(doc_instance.build.called)

if __name__ == '__main__':
    unittest.main()
