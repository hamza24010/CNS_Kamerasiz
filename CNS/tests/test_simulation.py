import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
import importlib

# --- Mocking sys.modules to avoid importing full logic chain ---
sys.modules['settings'] = MagicMock()
sys.modules['video'] = MagicMock()
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['PyQt5'] = MagicMock()
sys.modules['PyQt5.QtWidgets'] = MagicMock()
sys.modules['PyQt5.QtCore'] = MagicMock()
sys.modules['PyQt5.QtGui'] = MagicMock()
sys.modules['matplotlib.backends.backend_qt5agg'] = MagicMock()

import CNS.mainS as mainS

class TestISPM15Simulator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Reload mainS to ensure fresh state, though settings object persists
        importlib.reload(mainS)

    def setUp(self):
        # Always access settings through mainS.settings to handle reloads
        self.settings = mainS.settings

    @patch('CNS.mainS.requests.get')
    def test_initialization_defaults(self, mock_get):
        """Test simulator initialization with default efficiency (0.5)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'lat': 0, 'lon': 0, 'city': 'TestCity',
            'current_weather': {'temperature': 25.0}
        }
        mock_get.return_value = mock_response

        # Configure settings on the live object
        self.settings.SIM_IS_RANDOM = False
        self.settings.SIM_EFFICIENCY = 0.5
        self.settings.DESIRED_SECONDS = 60

        sim = mainS.ISPM15Simulator()

        self.assertEqual(sim.efficiency, 0.5)
        self.assertEqual(sim.start_temp, 25.0)
        self.assertAlmostEqual(sim.p_heat_rate, 0.635, places=3)

    @patch('CNS.mainS.requests.get')
    def test_initialization_random(self, mock_get):
        """Test simulator initialization with random efficiency"""
        mock_get.side_effect = Exception("API Error")

        self.settings.SIM_IS_RANDOM = True

        sim = mainS.ISPM15Simulator()

        self.assertTrue(0.0 <= sim.efficiency <= 1.0)

    @patch('CNS.mainS.requests.get')
    def test_gap_control(self, mock_get):
        """Test that sensors don't exceed ambient - gap"""
        mock_get.side_effect = Exception("API Error")

        self.settings.SIM_IS_RANDOM = False
        self.settings.SIM_EFFICIENCY = 0.0 # Low efficiency -> Large Gap (30.0)
        self.settings.DESIRED_SECONDS = 60
        self.settings.RESISTANCE_MAX = 200
        self.settings.RESISTANCE_MIN = 100

        sim = mainS.ISPM15Simulator()

        # Verify target gap attribute
        self.assertEqual(sim.target_gap, 30.0)

if __name__ == '__main__':
    unittest.main()
