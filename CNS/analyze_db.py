import sqlite3
import os
import sys
import datetime
import math

# Use relative path or find the absolute path dynamically
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, "mainDb.sqlite")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get the Report ID 97 (as seen before, it had data)
    report_id = 97
    print(f"--- ANALYZING REPORT ID: {report_id} ---")
    
    # Get all sensor data
    # Columns:
    # 0-12: T1..T13
    # 13-14: AT1, AT2
    # 15: STEPNO (Not needed if we order by ID)
    # 16: STEPTIME (Timestamp)
    
    query = f"""
    SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME
    FROM Report_Details
    WHERE REPORT_ID={report_id}
    ORDER BY ID ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if not rows:
        print("No data found.")
        sys.exit()

    # Parse Data
    data = {f"T{i+1}": [] for i in range(13)}
    data["AT1"] = []
    data["AT2"] = []
    timestamps = []

    for r in rows:
        # Check if row is valid (sometimes 00.00 is used for null/start)
        # We will parse all, handle 0.0 later
        try:
            ts = datetime.datetime.strptime(r[15], "%Y-%m-%d %H:%M:%S")
        except:
            continue

        timestamps.append(ts)

        for i in range(13):
            val = float(r[i])
            data[f"T{i+1}"].append(val)

        data["AT1"].append(float(r[13]))
        data["AT2"].append(float(r[14]))

    # 1. Analyze Time Intervals
    deltas = []
    for i in range(1, len(timestamps)):
        diff = (timestamps[i] - timestamps[i-1]).total_seconds()
        deltas.append(diff)
        
    avg_step_seconds = sum(deltas) / len(deltas)
    print(f"Average Step Duration: {avg_step_seconds:.2f} seconds")
    
    # 2. Calculate Heating Coefficients (k)
    # Model: dT/dt = k * (T_amb - T_sensor)
    # k = (dT/dt) / (T_amb - T_sensor)
    # We will estimate k for each step where T_amb > T_sensor + 2 (to avoid noise near equilibrium)
    
    sensor_k_values = {}
    
    for key in data:
        if key.startswith("AT"): continue # Skip ambient for k calculation

        k_samples = []
        vals = data[key]
        ats = data["AT1"] # Use AT1 as reference ambient

        for i in range(1, len(vals)):
            t_curr = vals[i]
            t_prev = vals[i-1]
            at_prev = ats[i-1]
            dt = deltas[i-1] / 60.0 # in minutes

            if dt <= 0: continue

            diff = at_prev - t_prev
            change = t_curr - t_prev

            # Filter for valid heating phase
            # We want cases where ambient is significantly hotter than sensor
            if diff > 5.0 and change > 0:
                k = (change / dt) / diff
                if 0 < k < 1.0: # Filter outliers
                    k_samples.append(k)

        if k_samples:
            avg_k = sum(k_samples) / len(k_samples)
            sensor_k_values[key] = avg_k
        else:
            sensor_k_values[key] = 0.0

    print("\n--- ESTIMATED K VALUES (per minute) ---")
    sorted_sensors = sorted(sensor_k_values.items(), key=lambda x: x[1])
    for s, k in sorted_sensors:
        print(f"{s}: {k:.5f}")

    # 3. Analyze Noise / Fluctuations
    # We can look at the difference between actual value and a moving average
    print("\n--- NOISE ANALYSIS (Std Dev of Residuals) ---")
    for key in data:
        vals = data[key]
        if len(vals) < 5: continue
        
        # Simple noise est: diff from 3-point average
        residuals = []
        for i in range(1, len(vals)-1):
            avg = (vals[i-1] + vals[i+1]) / 2.0
            res = vals[i] - avg
            residuals.append(res)

        if residuals:
            # Standard deviation
            mean_res = sum(residuals) / len(residuals)
            variance = sum((x - mean_res) ** 2 for x in residuals) / len(residuals)
            std_dev = math.sqrt(variance)
            print(f"{key}: {std_dev:.4f}")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
