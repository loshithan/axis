"""
AXIS Demo Data Seeder
Populates the database with realistic demo data for Hospitals and Mobility SBUs.
Run: python db/seed.py
"""
import json
import os
import psycopg2
from datetime import date, time, timedelta

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://axis_user:axis_dev_password@localhost:5432/axis")


def seed():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("Seeding AXIS demo data...")

    # ── 1. SBUs ──
    for config_file in ["hospitals.json", "mobility.json"]:
        config_path = os.path.join(os.path.dirname(__file__), "..", "configs", config_file)
        with open(config_path, "r") as f:
            config = json.load(f)

        cur.execute("""
            INSERT INTO sbus (name, code, timezone, config)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET config = EXCLUDED.config
            RETURNING id
        """, (config["name"], config["sbu_code"], config["timezone"], json.dumps(config)))
        sbu_id = cur.fetchone()[0]
        print(f"  SBU: {config['name']} (id={sbu_id})")

        # ── 2. Departments ──
        dept_ids = {}
        for dept in config["departments"]:
            cur.execute("""
                INSERT INTO departments (sbu_id, name, code)
                VALUES (%s, %s, %s)
                ON CONFLICT (sbu_id, code) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
            """, (sbu_id, dept["name"], dept["code"]))
            dept_ids[dept["code"]] = cur.fetchone()[0]
            print(f"    Dept: {dept['name']}")

        # ── 3. Shift Types ──
        for st in config["shift_types"]:
            cur.execute("""
                INSERT INTO shift_types (sbu_id, name, code, start_time, end_time,
                    required_certifications, min_headcount, department_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sbu_id, code) DO UPDATE SET
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    required_certifications = EXCLUDED.required_certifications,
                    min_headcount = EXCLUDED.min_headcount
            """, (
                sbu_id, st["name"], st["code"],
                st["start_time"], st["end_time"],
                json.dumps(st["required_certifications"]),
                st["min_headcount"], st["department_code"]
            ))

    # ── 4. Workers (Hospitals) ──
    hospitals_workers = [
        # ICU Nurses
        {"eid": "HH-001", "name": "Amara Perera", "email": "amara@hemas.lk", "dept": "icu",
         "certs": ["icu_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-002", "name": "Kavinda Silva", "email": "kavinda@hemas.lk", "dept": "icu",
         "certs": ["icu_certified", "bls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-003", "name": "Nethmi Fernando", "email": "nethmi@hemas.lk", "dept": "icu",
         "certs": ["icu_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-004", "name": "Dinesh Rajapaksa", "email": "dinesh@hemas.lk", "dept": "icu",
         "certs": ["icu_certified", "bls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-005", "name": "Sachini Wickrama", "email": "sachini@hemas.lk", "dept": "icu",
         "certs": ["icu_certified", "bls", "registered_nurse"], "max_hrs": 36},
        {"eid": "HH-006", "name": "Ruwan Bandara", "email": "ruwan@hemas.lk", "dept": "icu",
         "certs": ["icu_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        # Emergency Nurses
        {"eid": "HH-011", "name": "Tharushi Jayawardena", "email": "tharushi@hemas.lk", "dept": "emergency",
         "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-012", "name": "Chamara Dissanayake", "email": "chamara@hemas.lk", "dept": "emergency",
         "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-013", "name": "Ishara Kumari", "email": "ishara@hemas.lk", "dept": "emergency",
         "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-014", "name": "Malith Perera", "email": "malith@hemas.lk", "dept": "emergency",
         "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-015", "name": "Priyanka De Silva", "email": "priyanka@hemas.lk", "dept": "emergency",
         "certs": ["emergency_certified", "bls", "registered_nurse"], "max_hrs": 36},
        {"eid": "HH-016", "name": "Nuwan Gamage", "email": "nuwan@hemas.lk", "dept": "emergency",
         "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        # General Ward
        {"eid": "HH-021", "name": "Sanduni Rathnayake", "email": "sanduni@hemas.lk", "dept": "ward_general",
         "certs": ["registered_nurse", "bls"], "max_hrs": 40},
        {"eid": "HH-022", "name": "Lakmal Jayasuriya", "email": "lakmal@hemas.lk", "dept": "ward_general",
         "certs": ["registered_nurse", "bls"], "max_hrs": 40},
        {"eid": "HH-023", "name": "Hashini Abeysekara", "email": "hashini@hemas.lk", "dept": "ward_general",
         "certs": ["registered_nurse"], "max_hrs": 40},
        {"eid": "HH-024", "name": "Asanka Wijesinghe", "email": "asanka@hemas.lk", "dept": "ward_general",
         "certs": ["registered_nurse", "bls"], "max_hrs": 40},
        {"eid": "HH-025", "name": "Dilhani Mendis", "email": "dilhani@hemas.lk", "dept": "ward_general",
         "certs": ["registered_nurse"], "max_hrs": 36},
    ]

    cur.execute("SELECT id FROM sbus WHERE code='hospitals'")
    hosp_sbu_id = cur.fetchone()[0]
    
    for w in hospitals_workers:
        cur.execute("SELECT id FROM departments WHERE sbu_id=%s AND code=%s", (hosp_sbu_id, w["dept"]))
        dept_row = cur.fetchone()
        if dept_row:
            cur.execute("""
                INSERT INTO workers (employee_id, name, email, department_id, certifications, max_weekly_hours)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id) DO NOTHING
            """, (w["eid"], w["name"], w["email"], dept_row[0], json.dumps(w["certs"]), w["max_hrs"]))

    # ── 5. Workers (Mobility) ──
    mobility_workers = [
        {"eid": "HM-001", "name": "Kasun Ratnayake", "email": "kasun@hemas.lk", "dept": "ground_crew",
         "certs": ["ground_ops_certified", "safety_trained", "aviation_certified"], "max_hrs": 48},
        {"eid": "HM-002", "name": "Thilina Weerasinghe", "email": "thilina@hemas.lk", "dept": "ground_crew",
         "certs": ["ground_ops_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-003", "name": "Nadeeka Subasinghe", "email": "nadeeka@hemas.lk", "dept": "ground_crew",
         "certs": ["ground_ops_certified", "safety_trained", "aviation_certified"], "max_hrs": 48},
        {"eid": "HM-004", "name": "Roshan Jayawickrama", "email": "roshan@hemas.lk", "dept": "ground_crew",
         "certs": ["ground_ops_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-005", "name": "Supun Herath", "email": "supun@hemas.lk", "dept": "ground_crew",
         "certs": ["ground_ops_certified", "safety_trained"], "max_hrs": 44},
        {"eid": "HM-011", "name": "Charith Mendis", "email": "charith@hemas.lk", "dept": "maritime_ops",
         "certs": ["maritime_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-012", "name": "Geethika Peiris", "email": "geethika@hemas.lk", "dept": "maritime_ops",
         "certs": ["maritime_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-013", "name": "Ashan Karunaratne", "email": "ashan@hemas.lk", "dept": "maritime_ops",
         "certs": ["maritime_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-021", "name": "Yamuna Liyanage", "email": "yamuna@hemas.lk", "dept": "dispatch",
         "certs": ["dispatch_certified"], "max_hrs": 48},
        {"eid": "HM-022", "name": "Prabath Wickramarachchi", "email": "prabath@hemas.lk", "dept": "dispatch",
         "certs": ["dispatch_certified"], "max_hrs": 48},
    ]

    cur.execute("SELECT id FROM sbus WHERE code='mobility'")
    mob_sbu_id = cur.fetchone()[0]

    for w in mobility_workers:
        cur.execute("SELECT id FROM departments WHERE sbu_id=%s AND code=%s", (mob_sbu_id, w["dept"]))
        dept_row = cur.fetchone()
        if dept_row:
            cur.execute("""
                INSERT INTO workers (employee_id, name, email, department_id, certifications, max_weekly_hours)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id) DO NOTHING
            """, (w["eid"], w["name"], w["email"], dept_row[0], json.dumps(w["certs"]), w["max_hrs"]))

    # ── 6. Availability (next 2 weeks for all workers) ──
    print("  Generating availability for next 2 weeks...")
    today = date.today()
    cur.execute("SELECT id FROM workers WHERE is_active = TRUE")
    all_worker_ids = [row[0] for row in cur.fetchall()]

    for worker_id in all_worker_ids:
        for day_offset in range(14):
            d = today + timedelta(days=day_offset)
            # Most workers available 06:00-22:00 on weekdays
            if d.weekday() < 5:  # Mon-Fri
                cur.execute("""
                    INSERT INTO availability (worker_id, date, start_time, end_time, is_available)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (worker_id, date, start_time) DO NOTHING
                """, (worker_id, d, time(5, 0), time(23, 0)))
            else:
                # 70% chance available on weekends
                import random
                if random.random() < 0.7:
                    cur.execute("""
                        INSERT INTO availability (worker_id, date, start_time, end_time, is_available)
                        VALUES (%s, %s, %s, %s, TRUE)
                        ON CONFLICT (worker_id, date, start_time) DO NOTHING
                    """, (worker_id, d, time(5, 0), time(23, 0)))

    conn.commit()
    cur.close()
    conn.close()
    print("Seeding complete!")


if __name__ == "__main__":
    seed()
