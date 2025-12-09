import sqlite3
import os
import sys
import datetime
import math

# Allow passing db name as argument
db_name = sys.argv[1] if len(sys.argv) > 1 else "mainDb1.sqlite"
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, db_name)

print(f"--- ANALYZING DATABASE: {db_name} ---")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find a report with significant data
    cursor.execute("SELECT ID, START_TIME, TYPE, REPORT_INFO FROM REPORT ORDER BY ID DESC LIMIT 10")
    reports = cursor.fetchall()
    
    target_report_id = None
    max_steps = 0

    for r in reports:
        rid = r[0]
        cursor.execute(f"SELECT COUNT(*) FROM Report_Details WHERE REPORT_ID={rid}")
        count = cursor.fetchone()[0]
        if count > 50: # Assume valid report has > 50 steps
            target_report_id = rid
            max_steps = count
            break

    if not target_report_id:
        print("No valid long report found.")
        sys.exit()

    print(f"Selected Report ID: {target_report_id} with {max_steps} steps")
    
    query = f"""
    SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME
    FROM Report_Details
    WHERE REPORT_ID={target_report_id}
    ORDER BY ID ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    # Parse Data
    data = {f"T{i+1}": [] for i in range(13)}
    data["AT1"] = []
    data["AT2"] = []
    timestamps = []

    for r in rows:
        try:
            ts = datetime.datetime.strptime(r[15], "%Y-%m-%d %H:%M:%S")
        except:
            continue

        timestamps.append(ts)

        for i in range(13):
            # Handle empty strings or 0.00
            try:
                val = float(r[i])
            except:
                val = 0.0
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
    sensor_k_values = {}
    
    # Find heating phase: AT increasing and > 40

    for key in data:
        if key.startswith("AT"): continue

        k_samples = []
        vals = data[key]
        ats = data["AT1"]

        for i in range(1, len(vals)):
            t_curr = vals[i]
            t_prev = vals[i-1]
            at_prev = ats[i-1]
            dt = deltas[i-1] / 60.0 # minutes

            if dt <= 0: continue
            if t_prev == 0.0: continue # Skip invalid data

            diff = at_prev - t_prev
            change = t_curr - t_prev

            # Robust filter for heating phase
            if diff > 10.0 and change > 0.05:
                k = (change / dt) / diff
                if 0.001 < k < 0.1: # Reasonable range for wood
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

    # 3. Ambient Analysis
    at1 = data["AT1"]
    at_rise = []
    for i in range(1, len(at1)):
        dt = deltas[i-1] / 60.0
        if dt > 0 and at1[i] > at1[i-1]:
            rate = (at1[i] - at1[i-1]) / dt
            if rate < 5.0: # Filter spikes
                at_rise.append(rate)

    if at_rise:
        avg_rise = sum(at_rise) / len(at_rise)
        print(f"\nAvg Ambient Heating Rate: {avg_rise:.4f} C/min")

    # 4. Noise Analysis
    print("\n--- NOISE ANALYSIS (Std Dev) ---")
    for key in ["AT1", "AT2", "T1", "T5", "T13"]: # Sample sensors
        vals = [v for v in data[key] if v > 10]
        if len(vals) < 10: continue
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
