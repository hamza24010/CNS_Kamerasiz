import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import importlib

# --- Mocking dependencies ---
sys.modules['settings'] = MagicMock()
sys.modules['video'] = MagicMock()
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()

# Define dummy QWidget and QDialog
class MockQWidget:
    def __init__(self, parent=None):
        pass
    def setWindowTitle(self, title):
        pass
    def resize(self, w, h):
        pass
    def show(self):
        pass
    def close(self):
        pass
    def setLayout(self, layout):
        pass

class MockQDialog(MockQWidget):
    def exec_(self):
        pass

class MockQCheckBox(MockQWidget):
    def __init__(self, text=None, parent=None):
        self.toggled = MagicMock() # Signal must be an object with .connect
        pass
    def setChecked(self, checked):
        pass
    def isChecked(self):
        return False

mock_qt_widgets = MagicMock()
mock_qt_widgets.QWidget = MockQWidget
mock_qt_widgets.QDialog = MockQDialog
mock_qt_widgets.QApplication = MagicMock()
mock_qt_widgets.QLabel = MagicMock()
mock_qt_widgets.QPushButton = MagicMock()
mock_qt_widgets.QVBoxLayout = MagicMock()
mock_qt_widgets.QHBoxLayout = MagicMock()
mock_qt_widgets.QSpinBox = MagicMock
mock_qt_widgets.QDoubleSpinBox = MagicMock
mock_qt_widgets.QCheckBox = MockQCheckBox
mock_qt_widgets.QLineEdit = MagicMock
mock_qt_widgets.QMessageBox = MagicMock()

mock_qt_core = MagicMock()
mock_qt_core.pyqtSignal = MagicMock()
mock_qt_core.Qt = MagicMock()

sys.modules['PyQt5'] = MagicMock()
sys.modules['PyQt5.QtWidgets'] = mock_qt_widgets
sys.modules['PyQt5.QtCore'] = mock_qt_core
sys.modules['PyQt5.QtGui'] = MagicMock()
sys.modules['matplotlib.backends.backend_qt5agg'] = MagicMock()

import CNS.mainS as mainS

class TestAdminPanel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # We assume mainS is loaded.
        pass

    def setUp(self):
        # Ensure we are modifying the current settings object attached to mainS
        mainS.settings.fan_right_pin = 20
        mainS.settings.resistance_pin = 16
        mainS.settings.DESIRED_ENGINE_MUNITE = 5
        mainS.settings.ENGINE_RESTING_MUNITE = 2
        mainS.settings.RESISTANCE_WORK_MIN = 3
        mainS.settings.RESISTANCE_REST_MIN = 1
        mainS.settings.SIM_IS_RANDOM = True
        mainS.settings.SIM_EFFICIENCY = 0.5
        mainS.settings.SLOW_SENSORS = [1,2,3,4]
        mainS.settings.CAMERA_ENABLED = False

    @patch('CNS.mainS.save_settings_to_file')
    @patch('CNS.mainS.QMessageBox')
    def test_admin_panel_save(self, mock_msgbox, mock_save_file):
        panel = mainS.AdminPanel()

        def set_val(layout_widget_tuple, val):
            widget = layout_widget_tuple[1]
            widget.value.return_value = val

        def set_text(layout_widget_tuple, val):
            widget = layout_widget_tuple[1]
            widget.text.return_value = val

        set_val(panel.inp_fan_work, 10)
        set_val(panel.inp_fan_rest, 5)
        set_val(panel.inp_rez_work, 20)
        set_val(panel.inp_rez_rest, 10)
        set_val(panel.inp_fan_pin, 25)
        set_val(panel.inp_rez_pin, 13)
        set_val(panel.inp_efficiency, 0.8)

        panel.chk_random.isChecked = MagicMock(return_value=False)
        panel.chk_camera.isChecked = MagicMock(return_value=True)

        set_text(panel.inp_slow_sensors, "1, 5, 9")

        panel.save_settings()

        if not mock_save_file.called:
            print("DEBUG: save_settings_to_file not called.")
            if mock_msgbox.critical.called:
                print(f"DEBUG: Critical Error: {mock_msgbox.critical.call_args}")

        self.assertTrue(mock_save_file.called)
        args, _ = mock_save_file.call_args
        saved_dict = args[1]

        self.assertEqual(saved_dict['DESIRED_ENGINE_MUNITE'], 10)
        self.assertEqual(saved_dict['SIM_IS_RANDOM'], False)
        self.assertEqual(saved_dict['CAMERA_ENABLED'], True)
        self.assertEqual(saved_dict['SLOW_SENSORS'], [1, 5, 9])

if __name__ == '__main__':
    unittest.main()
