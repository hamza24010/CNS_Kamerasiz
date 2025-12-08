import sqlite3
import os
import sys

db_path = r"c:\Users\hamza\Downloads\CNS\original program\mainDb.sqlite"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Get Reports
    print("--- REPORTS ---")
    cursor.execute("SELECT ID, START_TIME, TYPE, REPORT_INFO FROM REPORT ORDER BY ID DESC LIMIT 5")
    reports = cursor.fetchall()
    for r in reports:
        print(r)
        
    if not reports:
        print("No reports found.")
        sys.exit()
        
    # 2. Analyze the latest report (assuming it's the real one)
    # Or try to find one with many steps
    latest_id = reports[0][0]
    print(f"\n--- ANALYZING REPORT ID: {latest_id} ---")
    
    cursor.execute(f"SELECT T1, T2, T3, T4, AT1, AT2, STEPTIME FROM Report_Details WHERE REPORT_ID={latest_id} ORDER BY ID ASC")
    details = cursor.fetchall()
    
    if not details:
        print("No details found for this report.")
        sys.exit()
        
    print(f"Total Steps: {len(details)}")
    
    # Extract Data
    at1_vals = [float(x[4]) for x in details if x[4]]
    t1_vals = [float(x[0]) for x in details if x[0]]
    
    if not at1_vals:
        print("No AT1 data.")
        sys.exit()
        
    # Stats
    min_at = min(at1_vals)
    max_at = max(at1_vals)
    avg_at = sum(at1_vals) / len(at1_vals)
    
    print(f"AT1 Min: {min_at}")
    print(f"AT1 Max: {max_at}")
    print(f"AT1 Avg: {avg_at}")
    
    # Heating Rate (First 10 mins or until max)
    # Assuming 1 step = 1 minute (or check STEPTIME)
    # Let's just look at the first rise
    start_temp = at1_vals[0]
    peak_temp = max_at
    peak_index = at1_vals.index(peak_temp)
    
    if peak_index > 0:
        rise = peak_temp - start_temp
        rate = rise / peak_index # degrees per step
        print(f"Initial Heating Rate: {rate:.4f} deg/step (over {peak_index} steps)")
        
    # Spread (Difference between sensors)
    # Let's look at T1 vs T4 (just as an example of spread)
    if t1_vals:
        t4_vals = [float(x[3]) for x in details if x[3]]
        spreads = [abs(a-b) for a,b in zip(t1_vals, t4_vals)]
        max_spread = max(spreads)
        avg_spread = sum(spreads) / len(spreads)
        print(f"Max T1-T4 Spread: {max_spread:.4f}")
        print(f"Avg T1-T4 Spread: {avg_spread:.4f}")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
