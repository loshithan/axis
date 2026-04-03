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
        if not os.path.exists(config_path):
            config_path = os.path.join(os.path.dirname(__file__), "configs", config_file)
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
        {"eid": "HH-001", "name": "Amara Perera", "email": "amaraperera2026@yopmail.com", "dept": "icu",
         "type": "nurse", "certs": ["icu_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-002", "name": "Kavinda Silva", "email": "kavindasilva2026@yopmail.com", "dept": "icu",
         "type": "nurse", "certs": ["icu_certified", "bls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-003", "name": "Nethmi Fernando", "email": "nethmifernando2026@yopmail.com", "dept": "icu",
         "type": "nurse", "certs": ["icu_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-004", "name": "Dinesh Rajapaksa", "email": "dineshrajapaksa2026@yopmail.com", "dept": "icu",
         "type": "nurse", "certs": ["icu_certified", "bls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-005", "name": "Sachini Wickrama", "email": "sachiniwickrama2026@yopmail.com", "dept": "icu",
         "type": "nurse", "certs": ["icu_certified", "bls", "registered_nurse"], "max_hrs": 36},
        {"eid": "HH-006", "name": "Ruwan Bandara", "email": "ruwanbandara2026@yopmail.com", "dept": "icu",
         "type": "nurse", "certs": ["icu_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        # ICU Doctors
        {"eid": "HH-007", "name": "Dr. Pradeep Samarasinghe", "email": "pradeepsamarasinghe2026@yopmail.com", "dept": "icu",
         "type": "doctor", "certs": ["icu_certified", "acls", "mbbs"], "max_hrs": 48},
        {"eid": "HH-008", "name": "Dr. Chathuri Wimalasena", "email": "chathuriwimalasena2026@yopmail.com", "dept": "icu",
         "type": "doctor", "certs": ["icu_certified", "acls", "mbbs"], "max_hrs": 48},
        # Emergency Nurses
        {"eid": "HH-011", "name": "Tharushi Jayawardena", "email": "tharushijayawardena2026@yopmail.com", "dept": "emergency",
         "type": "nurse", "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-012", "name": "Chamara Dissanayake", "email": "chamaradissanayake2026@yopmail.com", "dept": "emergency",
         "type": "nurse", "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-013", "name": "Ishara Kumari", "email": "isharakumari2026@yopmail.com", "dept": "emergency",
         "type": "nurse", "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-014", "name": "Malith Perera", "email": "malithperera2026@yopmail.com", "dept": "emergency",
         "type": "nurse", "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        {"eid": "HH-015", "name": "Priyanka De Silva", "email": "priyankadesilva2026@yopmail.com", "dept": "emergency",
         "type": "nurse", "certs": ["emergency_certified", "bls", "registered_nurse"], "max_hrs": 36},
        {"eid": "HH-016", "name": "Nuwan Gamage", "email": "nuwangamage2026@yopmail.com", "dept": "emergency",
         "type": "nurse", "certs": ["emergency_certified", "bls", "acls", "registered_nurse"], "max_hrs": 40},
        # Emergency Doctors
        {"eid": "HH-017", "name": "Dr. Ruwani Gunawardena", "email": "ruwanigunawardena2026@yopmail.com", "dept": "emergency",
         "type": "doctor", "certs": ["emergency_certified", "acls", "mbbs"], "max_hrs": 48},
        {"eid": "HH-018", "name": "Dr. Harsha Nanayakkara", "email": "harshananaYakkara2026@yopmail.com", "dept": "emergency",
         "type": "doctor", "certs": ["emergency_certified", "acls", "mbbs"], "max_hrs": 48},
        # General Ward Nurses
        {"eid": "HH-021", "name": "Sanduni Rathnayake", "email": "sandunirathnayake2026@yopmail.com", "dept": "ward_general",
         "type": "nurse", "certs": ["registered_nurse", "bls"], "max_hrs": 40},
        {"eid": "HH-022", "name": "Lakmal Jayasuriya", "email": "lakmaljayasuriya2026@yopmail.com", "dept": "ward_general",
         "type": "nurse", "certs": ["registered_nurse", "bls"], "max_hrs": 40},
        {"eid": "HH-023", "name": "Hashini Abeysekara", "email": "hashiniabeysekara2026@yopmail.com", "dept": "ward_general",
         "type": "nurse", "certs": ["registered_nurse"], "max_hrs": 40},
        {"eid": "HH-024", "name": "Asanka Wijesinghe", "email": "asankawijesinghe2026@yopmail.com", "dept": "ward_general",
         "type": "nurse", "certs": ["registered_nurse", "bls"], "max_hrs": 40},
        {"eid": "HH-025", "name": "Dilhani Mendis", "email": "dilhanimendis2026@yopmail.com", "dept": "ward_general",
         "type": "nurse", "certs": ["registered_nurse"], "max_hrs": 36},
        # Operation Theatre
        {"eid": "HH-031", "name": "Dr. Suresh Amaratunga", "email": "sureshamaratunga2026@yopmail.com", "dept": "ot",
         "type": "doctor", "certs": ["mbbs", "surgery_certified", "acls"], "max_hrs": 48},
        {"eid": "HH-032", "name": "Dr. Nilmini Rodrigo", "email": "nilminirodrigo2026@yopmail.com", "dept": "ot",
         "type": "doctor", "certs": ["mbbs", "surgery_certified", "acls"], "max_hrs": 48},
        {"eid": "HH-033", "name": "Dr. Prasad Jayatilake", "email": "prasadjayatilake2026@yopmail.com", "dept": "ot",
         "type": "doctor", "certs": ["mbbs", "anesthesia_certified", "acls"], "max_hrs": 48},
        {"eid": "HH-034", "name": "Madhavi Seneviratne", "email": "madhaviseneviratne2026@yopmail.com", "dept": "ot",
         "type": "nurse", "certs": ["ot_certified", "registered_nurse", "bls"], "max_hrs": 40},
        {"eid": "HH-035", "name": "Chaminda Pathirana", "email": "chamindapathirana2026@yopmail.com", "dept": "ot",
         "type": "technician", "certs": ["ot_tech_certified", "safety_trained"], "max_hrs": 40},
    ]

    cur.execute("SELECT id FROM sbus WHERE code='hospitals'")
    hosp_sbu_id = cur.fetchone()[0]

    for w in hospitals_workers:
        cur.execute("SELECT id FROM departments WHERE sbu_id=%s AND code=%s", (hosp_sbu_id, w["dept"]))
        dept_row = cur.fetchone()
        if dept_row:
            cur.execute("""
                INSERT INTO workers (employee_id, name, email, department_id, employee_type, certifications, max_weekly_hours)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    employee_type = EXCLUDED.employee_type,
                    certifications = EXCLUDED.certifications
            """, (w["eid"], w["name"], w["email"], dept_row[0], w["type"], json.dumps(w["certs"]), w["max_hrs"]))

    # ── 5. Workers (Mobility) ──
    mobility_workers = [
        {"eid": "HM-001", "name": "Kasun Ratnayake", "email": "kasunratnayake2026@yopmail.com", "dept": "ground_crew",
         "type": "technician", "certs": ["ground_ops_certified", "safety_trained", "aviation_certified"], "max_hrs": 48},
        {"eid": "HM-002", "name": "Thilina Weerasinghe", "email": "thilinaweerasinghe2026@yopmail.com", "dept": "ground_crew",
         "type": "technician", "certs": ["ground_ops_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-003", "name": "Nadeeka Subasinghe", "email": "nadeekasubasinghe2026@yopmail.com", "dept": "ground_crew",
         "type": "technician", "certs": ["ground_ops_certified", "safety_trained", "aviation_certified"], "max_hrs": 48},
        {"eid": "HM-004", "name": "Roshan Jayawickrama", "email": "roshanjayawickrama2026@yopmail.com", "dept": "ground_crew",
         "type": "technician", "certs": ["ground_ops_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-005", "name": "Supun Herath", "email": "supunherath2026@yopmail.com", "dept": "ground_crew",
         "type": "technician", "certs": ["ground_ops_certified", "safety_trained"], "max_hrs": 44},
        {"eid": "HM-011", "name": "Charith Mendis", "email": "charithmendis2026@yopmail.com", "dept": "maritime_ops",
         "type": "technician", "certs": ["maritime_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-012", "name": "Geethika Peiris", "email": "geethikapeiris2026@yopmail.com", "dept": "maritime_ops",
         "type": "technician", "certs": ["maritime_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-013", "name": "Ashan Karunaratne", "email": "ashankarunaratne2026@yopmail.com", "dept": "maritime_ops",
         "type": "technician", "certs": ["maritime_certified", "safety_trained"], "max_hrs": 48},
        {"eid": "HM-021", "name": "Yamuna Liyanage", "email": "yamunaliyanage2026@yopmail.com", "dept": "dispatch",
         "type": "admin", "certs": ["dispatch_certified"], "max_hrs": 48},
        {"eid": "HM-022", "name": "Prabath Wickramarachchi", "email": "prabathwickramarachchi2026@yopmail.com", "dept": "dispatch",
         "type": "admin", "certs": ["dispatch_certified"], "max_hrs": 48},
    ]

    cur.execute("SELECT id FROM sbus WHERE code='mobility'")
    mob_sbu_id = cur.fetchone()[0]

    for w in mobility_workers:
        cur.execute("SELECT id FROM departments WHERE sbu_id=%s AND code=%s", (mob_sbu_id, w["dept"]))
        dept_row = cur.fetchone()
        if dept_row:
            cur.execute("""
                INSERT INTO workers (employee_id, name, email, department_id, employee_type, certifications, max_weekly_hours)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    employee_type = EXCLUDED.employee_type,
                    certifications = EXCLUDED.certifications
            """, (w["eid"], w["name"], w["email"], dept_row[0], w["type"], json.dumps(w["certs"]), w["max_hrs"]))

    # ── 6. Availability (next 90 days for all workers) ──
    print("  Generating availability for next 90 days...")
    import random
    today = date.today()
    cur.execute("SELECT id FROM workers WHERE is_active = TRUE")
    all_worker_ids = [row[0] for row in cur.fetchall()]

    for worker_id in all_worker_ids:
        for day_offset in range(90):
            d = today + timedelta(days=day_offset)
            # Weekdays: always available 00:00-23:59
            if d.weekday() < 5:
                cur.execute("""
                    INSERT INTO availability (worker_id, date, start_time, end_time, is_available)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (worker_id, date, start_time) DO NOTHING
                """, (worker_id, d, time(0, 0), time(23, 59)))
            else:
                # 70% chance available on weekends
                if random.random() < 0.7:
                    cur.execute("""
                        INSERT INTO availability (worker_id, date, start_time, end_time, is_available)
                        VALUES (%s, %s, %s, %s, TRUE)
                        ON CONFLICT (worker_id, date, start_time) DO NOTHING
                    """, (worker_id, d, time(0, 0), time(23, 59)))

    conn.commit()
    cur.close()
    conn.close()
    print("Seeding complete!")


if __name__ == "__main__":
    seed()
