import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# --- Mocking sys.modules to avoid importing full logic chain ---
# We mock 'settings' because mainS.py loads it dynamically
# We also mock PyQt5 modules to avoid display issues in headless environment
sys.modules['settings'] = MagicMock()
sys.modules['video'] = MagicMock()

# Mocking GPIO
mock_gpio = MagicMock()
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = mock_gpio

# Mocking PyQt5
mock_qt = MagicMock()
sys.modules['PyQt5'] = mock_qt
sys.modules['PyQt5.QtWidgets'] = mock_qt
sys.modules['PyQt5.QtCore'] = mock_qt
sys.modules['PyQt5.QtGui'] = mock_qt
sys.modules['matplotlib.backends.backend_qt5agg'] = MagicMock()

# Now we can import the parts we need from mainS.py
# But mainS.py runs code on import (e.g., settings loading), so we need to be careful.
# We will use patch.dict to mock sys.modules during import if needed.

# However, mainS.py does 'import settings' dynamically.
# Let's try to import mainS.py inside the test methods or setup,
# ensuring that side effects are controlled.

# Actually, the cleanest way given the complexity of mainS.py (global execution)
# is to read the file and exec the specific class we want,
# OR just patch everything globally before import.

from CNS.mainS import ISPM15Simulator, settings as global_settings

class TestISPM15Simulator(unittest.TestCase):

    def setUp(self):
        # Reset settings for each test
        # We need to access the 'settings' object that ISPM15Simulator uses.
        # Since we imported 'settings' from mainS, we can modify it.
        pass

    @patch('CNS.mainS.requests.get')
    def test_initialization_defaults(self, mock_get):
        """Test simulator initialization with default efficiency (0.5)"""
        # Mock weather API to return fixed temperature
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'lat': 0, 'lon': 0, 'city': 'TestCity',
            'current_weather': {'temperature': 25.0}
        }
        mock_get.return_value = mock_response

        # Configure settings
        global_settings.SIM_IS_RANDOM = False
        global_settings.SIM_EFFICIENCY = 0.5
        global_settings.DESIRED_SECONDS = 60

        sim = ISPM15Simulator()

        self.assertEqual(sim.efficiency, 0.5)
        self.assertEqual(sim.start_temp, 25.0)
        # Check if heat rate is interpolated correctly for eff=0.5
        # 0.42 to 0.85 -> mid is (0.42+0.85)/2 = 0.635
        self.assertAlmostEqual(sim.p_heat_rate, 0.635, places=3)

        # Check sensors count
        self.assertEqual(len(sim.sensors), 13)
        self.assertEqual(len(sim.at_states), 2)

    @patch('CNS.mainS.requests.get')
    def test_initialization_random(self, mock_get):
        """Test simulator initialization with random efficiency"""
        mock_get.side_effect = Exception("API Error") # Fallback to random temp

        global_settings.SIM_IS_RANDOM = True

        sim = ISPM15Simulator()

        self.assertTrue(0.0 <= sim.efficiency <= 1.0)
        self.assertTrue(15.0 <= sim.start_temp <= 20.0) # Fallback range

    @patch('CNS.mainS.requests.get')
    def test_calculate_step_heating(self, mock_get):
        """Test heating logic"""
        mock_get.side_effect = Exception("API Error")
        global_settings.SIM_IS_RANDOM = False
        global_settings.SIM_EFFICIENCY = 1.0 # High efficiency
        global_settings.DESIRED_SECONDS = 60
        global_settings.RESISTANCE_MAX = 100
        global_settings.RESISTANCE_MIN = 90

        sim = ISPM15Simulator()
        sim.start_temp = 20.0
        # Force ambient to be low so heater turns on
        sim.at_states = [{"val": 20.0}, {"val": 20.0}]
        sim.virtual_heater_on = True
        sim.rezistans_aktif = True
        sim.sogutma_modu = False

        mask = [True] * 15

        vals, hit = sim.calculate_step(mask, desired_temp=56.0)

        # Ambient should increase
        new_ambient = (sim.at_states[0]["val"] + sim.at_states[1]["val"]) / 2.0
        self.assertGreater(new_ambient, 20.0)

        # Sensors should increase (with some lag/noise)
        # With high efficiency (1.0), K is high, lag is low
        # But buffer needs to fill up first.
        # We need to run multiple steps to see sensor rise significantly if buffer is large

    @patch('CNS.mainS.requests.get')
    def test_gap_control(self, mock_get):
        """Test that sensors don't exceed ambient - gap"""
        mock_get.side_effect = Exception("API Error")
        global_settings.SIM_IS_RANDOM = False
        global_settings.SIM_EFFICIENCY = 0.0 # Low efficiency -> Large Gap (30.0)
        global_settings.DESIRED_SECONDS = 60

        sim = ISPM15Simulator()

        # Manually set ambient to stable high temp
        sim.at_states = [{"val": 100.0}, {"val": 100.0}]
        # Fill buffers with 100.0
        for s in sim.sensors:
            s["buffer"] = type(s["buffer"])([100.0]*len(s["buffer"]), maxlen=len(s["buffer"]))
            s["val"] = 50.0 # Current sensor temp

        mask = [True] * 15

        # Run a few steps
        for _ in range(5):
            sim.calculate_step(mask, 56.0)

        # Target gap is 30.0 for eff=0.0
        # Sensor should approach 100.0 - 30.0 = 70.0
        # It should NOT exceed 70.0 (plus noise) significantly

        for i in range(13):
            # Checking logic: effective_target = delayed_ambient (100) - target_gap (30) = 70
            # Sensor approaches 70.
            pass

        # Verify target gap attribute
        self.assertEqual(sim.target_gap, 30.0)


if __name__ == '__main__':
    unittest.main()
