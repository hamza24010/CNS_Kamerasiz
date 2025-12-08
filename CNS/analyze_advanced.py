import sqlite3
import os
import sys
import numpy as np

def analyze_db(db_name, force_report_id=None):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, db_name)

    print(f"\n{'='*40}")
    print(f"ANALYZING: {db_name}")
    print(f"{'='*40}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if force_report_id:
            report_id = force_report_id
            cursor.execute(f"SELECT COUNT(*) FROM Report_Details WHERE REPORT_ID={report_id}")
            total_steps = cursor.fetchone()[0]
        else:
            # Fallback to finding one
            cursor.execute("SELECT ID, COUNT(*) as cnt FROM Report_Details GROUP BY REPORT_ID ORDER BY cnt DESC LIMIT 1")
            res = cursor.fetchone()
            if res:
                report_id = res[0]
                total_steps = res[1]
            else:
                 print("No reports found")
                 return

        print(f"Using Report ID: {report_id} (Steps: {total_steps})")

        # Fetch Data
        query = f"""
        SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2
        FROM Report_Details
        WHERE REPORT_ID={report_id}
        ORDER BY ID ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            print("Rows are empty.")
            return

        # Parse into list of lists first
        data_list = []
        for r in rows:
            row_vals = []
            for x in r:
                try:
                    if x is None or x == '':
                        val = 0.0
                    else:
                        val = float(x)
                except:
                    val = 0.0
                row_vals.append(val)
            data_list.append(row_vals)

        data = np.array(data_list)

        # Filter out rows where AT1 <= 0
        valid_mask = data[:, 13] > 0
        data = data[valid_mask]

        steps = len(data)
        if steps < 10:
            print("Not enough valid data steps (<10).")
            return

        # 1. AMBIENT ANALYSIS
        at_avg = (data[:, 13] + data[:, 14]) / 2.0
        at_max = np.max(at_avg)
        at_min = np.min(at_avg)
        at_start = at_avg[0]

        print(f"\n--- AMBIENT ---")
        print(f"Start: {at_start:.2f}, Max: {at_max:.2f}")

        # Heating Phase (Start to Peak)
        peak_idx = np.argmax(at_avg)
        if peak_idx > 10:
            heating_rate = (at_avg[peak_idx] - at_start) / peak_idx
            print(f"Time to Peak: {peak_idx} steps")
            print(f"Avg Heating Rate: {heating_rate:.4f} C/step")
        else:
            print("Peak reached too early or at start.")
            peak_idx = steps - 1 # Use full range if peak is weird

        # 2. CORE SENSOR ANALYSIS (RELATIONSHIP)
        print(f"\n--- CORE SENSORS (T1-T13) ---")

        core_sensors = data[:, 0:13]

        # Filter active sensors (Max > 20 and not constantly 0)
        active_indices = []
        for i in range(13):
            if np.max(core_sensors[:, i]) > 20 and np.mean(core_sensors[:, i]) > 1:
                active_indices.append(i)

        print(f"Active Sensors: {[i+1 for i in active_indices]}")

        if not active_indices:
            print("No active core sensors found.")
            return

        delays = []
        max_temps = []
        k_values = []

        for i in active_indices:
            sensor_data = core_sensors[:, i]
            sensor_max = np.max(sensor_data)
            max_temps.append(sensor_max)

            # Dead Time: Step index where sensor rises by +2.0 C from start
            start_val = sensor_data[0]
            if start_val < 1: start_val = at_start

            rise_indices = np.where(sensor_data > start_val + 2.0)[0]
            if len(rise_indices) > 0:
                dead_time = rise_indices[0]
            else:
                dead_time = 0
            delays.append(dead_time)

            # K Calculation
            ks = []
            calc_end = min(peak_idx, steps-1)
            for t in range(dead_time + 1, calc_end):
                dT = sensor_data[t] - sensor_data[t-1]
                delta = at_avg[t-1] - sensor_data[t-1]
                if delta > 10.0 and dT > 0.05:
                    k = dT / delta
                    ks.append(k)

            avg_k = np.mean(ks) if ks else 0
            k_values.append(avg_k)

            print(f"T{i+1}: Max={sensor_max:.2f}, DeadTime={dead_time} steps, K={avg_k:.4f}")

        # 3. GLOBAL STATS
        if delays:
            print(f"\nAvg Dead Time: {np.mean(delays):.1f} steps")
        if k_values:
            print(f"Avg K: {np.mean(k_values):.4f}")
            print(f"Min K: {np.min(k_values):.4f}")
            print(f"Max K: {np.max(k_values):.4f}")

        # 4. GAP ANALYSIS
        if peak_idx < steps and active_indices:
            core_vals = core_sensors[peak_idx, active_indices]
            gap_at_peak = at_avg[peak_idx] - np.mean(core_vals)
            print(f"Gap at Ambient Peak: {gap_at_peak:.2f} C")

        if active_indices:
            core_vals_end = core_sensors[-1, active_indices]
            gap_at_end = at_avg[-1] - np.mean(core_vals_end)
            print(f"Gap at End: {gap_at_end:.2f} C")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_db("mainDb.sqlite", force_report_id=97)
    analyze_db("mainDb1.sqlite", force_report_id=77)
