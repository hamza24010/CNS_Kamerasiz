import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

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

# Import functions to test
from CNS.mainS import save_settings_to_file

# Import the helper function directly
import CNS.mainS

class TestSettingsUtils(unittest.TestCase):

    @patch("os.fsync")
    def test_save_settings_existing_key(self, mock_fsync):
        """Test updating an existing key in settings file"""
        initial_content = "SOME_KEY = 123\nANOTHER_KEY = 'abc'\n"
        new_values = {"SOME_KEY": 456}

        with patch("builtins.open", mock_open(read_data=initial_content)) as mock_file:
            save_settings_to_file("dummy_path.py", new_values)

            # Check what was written
            handle = mock_file()
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)

            self.assertIn("SOME_KEY = 456", written_content)
            self.assertIn("ANOTHER_KEY = 'abc'", written_content)

    @patch("os.fsync")
    def test_save_settings_new_key(self, mock_fsync):
        """Test adding a new key to settings file"""
        initial_content = "SOME_KEY = 123\n"
        new_values = {"NEW_KEY": "new_val"}

        with patch("builtins.open", mock_open(read_data=initial_content)) as mock_file:
            save_settings_to_file("dummy_path.py", new_values)

            handle = mock_file()
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)

            self.assertIn("SOME_KEY = 123", written_content)
            self.assertIn("NEW_KEY = 'new_val'", written_content)

    @patch("os.fsync")
    def test_save_settings_boolean(self, mock_fsync):
        """Test saving boolean values correctly"""
        initial_content = ""
        new_values = {"BOOL_TRUE": True, "BOOL_FALSE": False}

        with patch("builtins.open", mock_open(read_data=initial_content)) as mock_file:
            save_settings_to_file("dummy_path.py", new_values)

            handle = mock_file()
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)

            self.assertIn("BOOL_TRUE = True", written_content)
            self.assertIn("BOOL_FALSE = False", written_content)

    def test_get_rtsp_url(self):
        """Test RTSP URL generation logic using the helper function"""
        # We access the helper function from the module
        func = CNS.mainS.get_rtsp_url_helper

        # Test 1: Full RTSP URL
        self.assertEqual(func("rtsp://custom:554/path"), "rtsp://custom:554/path")

        # Test 2: Shorthand IP
        expected = "rtsp://admin:arscns35@192.168.0.104:554/cam/realmonitor?channel=1&subtype=0"
        self.assertEqual(func("0.104"), expected)

        # Test 3: Full IP
        expected = "rtsp://admin:arscns35@10.0.0.5:554/cam/realmonitor?channel=1&subtype=0"
        self.assertEqual(func("10.0.0.5"), expected)

        # Test 4: Comma replacement
        expected = "rtsp://admin:arscns35@192.168.1.20:554/cam/realmonitor?channel=1&subtype=0"
        self.assertEqual(func("192,168,1,20"), expected)

        # Test 5: Default (None or Empty)
        expected = "rtsp://admin:arscns35@192.168.1.9:554/cam/realmonitor?channel=1&subtype=0"
        self.assertEqual(func(None), expected)
        self.assertEqual(func(""), expected)

if __name__ == '__main__':
    unittest.main()
