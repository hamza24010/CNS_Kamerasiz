
import random
import math
from collections import deque
import requests

# Default configuration mimicking 'settings.py'
class Settings:
    # Simulation Parameters
    DESIRED_SECONDS = 60
    SIM_IS_RANDOM = True
    SIM_EFFICIENCY = 0.5
    RESISTANCE_MAX = 90.0
    RESISTANCE_MIN = 80.0

    # Can be extended as needed

settings = Settings()

def get_online_temperature():
    try:
        # 1. Get Location (IP-API)
        loc_resp = requests.get("http://ip-api.com/json/", timeout=2)
        if loc_resp.status_code == 200:
            data = loc_resp.json()
            lat = data['lat']
            lon = data['lon']

            # 2. Get Temperature (Open-Meteo)
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            w_resp = requests.get(weather_url, timeout=2)
            if w_resp.status_code == 200:
                w_data = w_resp.json()
                temp = w_data['current_weather']['temperature']
                return float(temp)

        raise Exception("API Error")

    except Exception as e:
        # Fallback: 15-20 degrees Celsius
        return random.uniform(15.0, 20.0)

class ISPM15Simulator:
    def __init__(self, config=None):
        """
        Initialize the simulator.
        :param config: Optional object with settings. If None, uses default Settings class.
        """
        global settings
        if config:
            settings = config

        self.start_temp = get_online_temperature()

        # --- PHYSICS MODEL 2.0 ---
        # Efficiency: 0.0 (Slow/Noisy) <-> 1.0 (Fast/Clean)
        if getattr(settings, 'SIM_IS_RANDOM', True):
            self.efficiency = random.random()
        else:
            self.efficiency = getattr(settings, 'SIM_EFFICIENCY', 0.5)
            self.efficiency = max(0.0, min(1.0, self.efficiency))

        # Parameter Interpolation
        def lerp(a, b, t): return a + t * (b - a)

        # Heating Rate: 0.42 (Slow) - 0.85 (Fast) C/min
        self.p_heat_rate = lerp(0.42, 0.85, self.efficiency)

        # Conductivity (K):
        # Slow Oven: 0.007 - 0.016
        # Fast Oven: 0.017 - 0.026
        self.p_k_min = lerp(0.007, 0.017, self.efficiency)
        self.p_k_max = lerp(0.016, 0.026, self.efficiency)

        # Thermal Inertia (Dead Time): 10 - 15 mins (Avg 12)
        self.dead_time_mins = lerp(15.0, 10.0, self.efficiency)

        # Target Gap: Slow=30 C, Fast=12 C
        self.target_gap = lerp(30.0, 12.0, self.efficiency)

        # Noise Levels (Std Dev)
        self.p_noise_amb = lerp(3.0, 2.0, self.efficiency)
        self.p_noise_prob = lerp(1.5, 0.35, self.efficiency)

        self.sensors = []

        # Buffer size for Dead Time
        # Each step takes settings.DESIRED_SECONDS
        steps_needed = int((self.dead_time_mins * 60) / settings.DESIRED_SECONDS)
        if steps_needed < 1: steps_needed = 1

        # 13 Sensors Setup
        for i in range(13):
            # Distribute K values
            factor = i / 12.0
            k = self.p_k_min + (factor * (self.p_k_max - self.p_k_min))
            k += random.uniform(-0.0005, 0.0005)

            # Buffer for thermal lag
            buf = deque([self.start_temp] * steps_needed, maxlen=steps_needed)

            self.sensors.append({
                "val": self.start_temp + random.uniform(-0.5, 0.5),
                "k": k,
                "buffer": buf
            })

        # Ambient Sensors (AT1, AT2)
        self.at_states = [
            {"val": self.start_temp},
            {"val": self.start_temp}
        ]

        self.rezistans_aktif = True
        self.sogutma_modu = False
        self.virtual_heater_on = True

    def calculate_step(self, active_sensors_mask, desired_temp):
        dt_minutes = settings.DESIRED_SECONDS / 60.0

        # 1. Virtual Thermostat
        avg_ortam = (self.at_states[0]["val"] + self.at_states[1]["val"]) / 2.0

        if avg_ortam >= settings.RESISTANCE_MAX:
            self.virtual_heater_on = False
        elif avg_ortam <= settings.RESISTANCE_MIN:
            self.virtual_heater_on = True

        effective_heating = self.rezistans_aktif and self.virtual_heater_on and not self.sogutma_modu

        # 2. Ambient Physics
        target_ambient_max = 105.0

        if effective_heating:
            # Heating rate decreases as we approach target
            gap = target_ambient_max - avg_ortam
            if gap < 0: gap = 0
            dynamic_rate = self.p_heat_rate * (gap / 50.0)
            if dynamic_rate > self.p_heat_rate: dynamic_rate = self.p_heat_rate
            if dynamic_rate < 0.1: dynamic_rate = 0.1

            base_change = dynamic_rate * dt_minutes
        else:
            # Cooling rate
            cooling_rate = 0.5 + (1.0 - self.efficiency) * 0.5
            base_change = -cooling_rate * dt_minutes

        for i in range(2):
            self.at_states[i]["val"] += base_change + random.gauss(0, 0.3)
            # Spread between sensors
            if i == 1: self.at_states[i]["val"] += random.uniform(-0.1, 0.1) * dt_minutes

        avg_ortam_curr = (self.at_states[0]["val"] + self.at_states[1]["val"]) / 2.0

        # 3. Probe Physics (Lag + Newton + Asymptotic Limit)
        output_values = [0.0] * 15
        current_takoz_vals = []

        for i in range(13):
            if active_sensors_mask[i]:
                s = self.sensors[i]

                # A. Add new ambient temp to buffer
                s["buffer"].append(avg_ortam_curr)

                # B. Delayed ambient temp
                delayed_ambient = s["buffer"][0]

                # C. Physical Limit (Gap Control)
                effective_target = delayed_ambient - self.target_gap

                # D. Newton's Law
                diff = effective_target - s["val"]

                if diff > 0:
                    delta_T = s["k"] * diff * dt_minutes
                else:
                    delta_T = s["k"] * diff * dt_minutes * 0.5

                s["val"] += delta_T

                # E. Noise
                noise = random.gauss(0, 0.4)
                if self.efficiency < 0.3 and random.random() < 0.005:
                    noise += random.choice([-1.5, 1.5])

                final_val = s["val"] + noise
                output_values[i] = final_val
                current_takoz_vals.append(final_val)

        # Ambient Sensors Output
        if active_sensors_mask[13]: output_values[13] = self.at_states[0]["val"] + random.gauss(0, self.p_noise_amb * 0.5)
        if active_sensors_mask[14]: output_values[14] = self.at_states[1]["val"] + random.gauss(0, self.p_noise_amb * 0.5)

        # 4. Target Check
        if not current_takoz_vals:
             min_takoz = avg_ortam_curr
        else:
             min_takoz = min(current_takoz_vals)

        target_hit = (min_takoz >= desired_temp)

        return output_values, target_hit
