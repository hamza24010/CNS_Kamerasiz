import unittest
from unittest.mock import MagicMock, patch, call
import sys
import time
import importlib

# --- Mocking dependencies ---
sys.modules['settings'] = MagicMock()
sys.modules['video'] = MagicMock()
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()

# Define a real QThread base class so DataUpdateThread is not a Mock itself
class MockQThread:
    def __init__(self):
        pass
    def start(self):
        self.run()
    def run(self):
        pass
    def wait(self):
        pass

# Setup Mock Qt Core
mock_qt_core = MagicMock()
mock_qt_core.QThread = MockQThread
mock_qt_core.pyqtSignal = MagicMock()

# Setup PyQt5 package
mock_pyqt5 = MagicMock()
mock_pyqt5.QtCore = mock_qt_core
mock_pyqt5.QtWidgets = MagicMock()
mock_pyqt5.QtGui = MagicMock()

sys.modules['PyQt5'] = mock_pyqt5
sys.modules['PyQt5.QtWidgets'] = mock_pyqt5.QtWidgets
sys.modules['PyQt5.QtCore'] = mock_qt_core
sys.modules['PyQt5.QtGui'] = mock_pyqt5.QtGui
sys.modules['matplotlib.backends.backend_qt5agg'] = MagicMock()

import CNS.mainS as mainS

class TestThreadLogic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        importlib.reload(mainS)

    def setUp(self):
        # Prepare a mock settings object
        self.mock_settings = MagicMock()
        self.mock_settings.DESIRED_SECONDS = 60
        self.mock_settings.DESIRED_ENGINE_MUNITE = 1
        self.mock_settings.ENGINE_RESTING_MUNITE = 1
        self.mock_settings.RESISTANCE_WORK_MIN = 1
        self.mock_settings.RESISTANCE_REST_MIN = 1
        self.mock_settings.fan_right_pin = 20
        self.mock_settings.resistance_pin = 16
        self.mock_settings.DESIRED_SUCCESS_COUNT = 5
        self.mock_settings.DESIRED_TEMP = 56
        self.mock_settings.sensor1 = True
        for i in range(2, 16): setattr(self.mock_settings, f'sensor{i}', True)

    @patch('CNS.mainS.load_settings_module')
    @patch('CNS.mainS.get_db')
    @patch('CNS.mainS.GPIO')
    @patch('CNS.mainS.time')
    @patch('CNS.mainS.requests')
    def test_relay_toggling(self, mock_requests, mock_time, mock_gpio, mock_get_db, mock_load_settings):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_load_settings.return_value = self.mock_settings

        mock_time.time.side_effect = None
        mock_time.time.return_value = 1000.0

        with patch('CNS.mainS.ISPM15Simulator') as MockSim:
            sim_instance = MockSim.return_value
            sim_instance.calculate_step.return_value = ([50.0]*15, False)
            sim_instance.sogutma_modu = False

            thread = mainS.DataUpdateThread(rid=1)

            start_time = 1000.0
            def time_gen():
                yield start_time
                yield start_time
                yield start_time
                yield start_time + 10 # Loop 1
                yield start_time + 61 # Loop 2
                yield start_time + 122 # Loop 3
                while True:
                    yield start_time + 300

            mock_time.time.side_effect = time_gen()

            def sleep_side_effect(seconds):
                # Only stop after enough iterations
                if mock_time.sleep.call_count >= 4:
                    thread.stop_event.set()
            mock_time.sleep.side_effect = sleep_side_effect

            thread.stop_event = MagicMock()
            # Allow enough checks
            thread.stop_event.is_set.side_effect = [False] * 10 + [True]

            thread.pause_event = MagicMock()
            thread.pause_event.is_set.return_value = False

            thread.run()

            calls = mock_gpio.output.call_args_list
            fan_calls = [c for c in calls if c[0][0] == 20]
            rez_calls = [c for c in calls if c[0][0] == 16]

            self.assertTrue(len(fan_calls) >= 2)
            self.assertTrue(len(rez_calls) >= 2)

    @patch('CNS.mainS.load_settings_module')
    @patch('CNS.mainS.get_db')
    @patch('CNS.mainS.GPIO')
    @patch('CNS.mainS.threading.Event')
    def test_database_insert_in_thread(self, mock_event_cls, mock_gpio, mock_get_db, mock_load_settings):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_load_settings.return_value = self.mock_settings

        with patch('CNS.mainS.ISPM15Simulator') as MockSim:
            sim_instance = MockSim.return_value
            sim_instance.calculate_step.return_value = ([50.0]*15, False)

            thread = mainS.DataUpdateThread(rid=99)
            thread.target_count = 100
            thread.counter = 0

            stop_event_mock = MagicMock()
            pause_event_mock = MagicMock()
            mock_event_cls.side_effect = [stop_event_mock, pause_event_mock]

            stop_event_mock.is_set.side_effect = [False, True, True]
            pause_event_mock.is_set.return_value = False

            with patch('CNS.mainS.time') as mock_t:
                mock_t.time.return_value = 1000.0
                mock_t.sleep = MagicMock()
                thread.run()

            self.assertTrue(mock_conn.execute.called)

if __name__ == '__main__':
    unittest.main()
