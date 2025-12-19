import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os
import numpy as np
import importlib

# --- Mocking dependencies ---
sys.modules['settings'] = MagicMock()

# Define dummy QWidget to avoid MagicMock inheritance issues
class MockQWidget:
    def __init__(self, parent=None):
        pass
    def setWindowTitle(self, title):
        pass
    def setGeometry(self, x, y, w, h):
        pass
    def show(self):
        pass
    def close(self):
        pass

class MockQThread:
    def __init__(self):
        pass
    def start(self):
        self.run()
    def run(self):
        pass # To be overridden or patched
    def wait(self):
        pass

mock_qt_widgets = MagicMock()
mock_qt_widgets.QWidget = MockQWidget
mock_qt_widgets.QApplication = MagicMock()
mock_qt_widgets.QLabel = MagicMock()
mock_qt_widgets.QPushButton = MagicMock()
mock_qt_widgets.QVBoxLayout = MagicMock()
mock_qt_widgets.QMessageBox = MagicMock()
mock_qt_widgets.QSizePolicy = MagicMock()

mock_qt_core = MagicMock()
mock_qt_core.pyqtSignal = MagicMock()
mock_qt_core.QTimer = MagicMock()
mock_qt_core.QThread = MockQThread

# Setup PyQt5 package structure correctly
mock_pyqt5 = MagicMock()
mock_pyqt5.QtWidgets = mock_qt_widgets
mock_pyqt5.QtCore = mock_qt_core
mock_pyqt5.QtGui = MagicMock()

sys.modules['PyQt5'] = mock_pyqt5
sys.modules['PyQt5.QtWidgets'] = mock_qt_widgets
sys.modules['PyQt5.QtCore'] = mock_qt_core
sys.modules['PyQt5.QtGui'] = mock_pyqt5.QtGui

# Import video module
import CNS.video as video

class TestVideoModule(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        importlib.reload(video)

    @patch('CNS.video.cv2')
    @patch('CNS.video.datetime')
    def test_draw_timestamp(self, mock_datetime, mock_cv2):
        # Setup
        mock_datetime.datetime.now.return_value.strftime.return_value = "2023-01-01 12:00:00"
        mock_cv2.getTextSize.return_value = ((100, 20), 5)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result_frame = video.draw_timestamp(frame)

        mock_cv2.rectangle.assert_called()
        mock_cv2.putText.assert_called()

    @patch('CNS.video.cv2')
    def test_video_worker_recording(self, mock_cv2):
        # Setup mocks for cv2 calls inside VideoWorker
        mock_cap = MagicMock()
        mock_writer = MagicMock()

        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.VideoWriter.return_value = mock_writer
        # Critical: getTextSize must return values to unpack
        mock_cv2.getTextSize.return_value = ((100, 20), 5)

        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, dummy_frame)

        worker = video.VideoWorker("rtsp://test", 1, 1, "/tmp", duration=0.1)
        worker.run()

        mock_cv2.VideoCapture.assert_called_with("rtsp://test")
        mock_cv2.VideoWriter.assert_called()
        self.assertTrue(mock_writer.write.called)

    @patch('CNS.video.cv2')
    @patch('CNS.video.QMessageBox')
    def test_kamera_vibe_logic(self, mock_msgbox, mock_cv2):
        with patch('os.makedirs'), patch('os.path.exists', return_value=True):
            mock_cv2.getTextSize.return_value = ((100, 20), 5)

            window = video.KameraVibe("rtsp://test", 1, start_phase=1)

            # Setup preview capture
            mock_preview_cap = MagicMock()
            window.preview_cap = mock_preview_cap

            # Setup Worker Mock correctly
            # VideoWorker should be mocked to return a mock instance
            with patch('CNS.video.VideoWorker') as MockWorkerClass:
                worker_instance = MockWorkerClass.return_value

                dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
                window.preview_cap.read.return_value = (True, dummy_frame)

                window.start_process()

                mock_cv2.imwrite.assert_called()
                worker_instance.start.assert_called()

                # Test state transition
                window._on_worker_done()
                self.assertEqual(window.process_idx, 2)

if __name__ == '__main__':
    unittest.main()
