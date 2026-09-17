import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4

DATABASE_NAME = Path(__file__).parent / "medication.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medication_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_group_id TEXT,
            patient_user_id INTEGER,
            medicine_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            food_instruction TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patient_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            patient_code TEXT UNIQUE,
            full_name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            blood_group TEXT,
            emergency_contact TEXT,
            allergies TEXT,
            medical_conditions TEXT,
            doctor_name TEXT,
            doctor_contact TEXT,
            additional_notes TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("PRAGMA table_info(medication_schedule)")
    medication_columns = {row[1] for row in cursor.fetchall()}
    if "patient_user_id" not in medication_columns:
        cursor.execute("ALTER TABLE medication_schedule ADD COLUMN patient_user_id INTEGER")

    cursor.execute("PRAGMA table_info(patient_profile)")
    profile_columns = {row[1] for row in cursor.fetchall()}
    if "patient_code" not in profile_columns:
        cursor.execute("ALTER TABLE patient_profile ADD COLUMN patient_code TEXT")
    cursor.execute("SELECT id, user_id FROM patient_profile WHERE patient_code IS NULL OR patient_code = ''")
    for row in cursor.fetchall():
        cursor.execute("UPDATE patient_profile SET patient_code=? WHERE id=?", (f"PAT-{row[1]:05d}", row[0]))

    cursor.execute("PRAGMA table_info(medication_schedule)")
    columns = {row[1] for row in cursor.fetchall()}
    if "schedule_group_id" not in columns:
        cursor.execute("ALTER TABLE medication_schedule ADD COLUMN schedule_group_id TEXT")
    cursor.execute("SELECT id FROM medication_schedule WHERE schedule_group_id IS NULL")
    for row in cursor.fetchall():
        cursor.execute("UPDATE medication_schedule SET schedule_group_id=? WHERE id=?", (str(uuid4()), row[0]))
    connection.commit()
    connection.close()


def save_schedule(schedule):
    if not schedule:
        return False
    connection = get_connection()
    cursor = connection.cursor()
    group_id = schedule[0].get("schedule_group_id") or str(uuid4())
    for dose in schedule:
        dose["schedule_group_id"] = group_id
    cursor.execute("SELECT COUNT(*) FROM medication_schedule WHERE schedule_group_id=?", (group_id,))
    if cursor.fetchone()[0] > 0:
        connection.close()
        return False
    for dose in schedule:
        dose_time = dose["time"]
        time_value = dose_time.strftime("%H:%M:%S") if hasattr(dose_time, "strftime") else str(dose_time)
        cursor.execute('''
            INSERT INTO medication_schedule
            (schedule_group_id, patient_user_id, medicine_name, dosage, date, time, food_instruction, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (group_id, dose.get("patient_user_id"), dose["medicine_name"], dose["dosage"], str(dose["date"]), time_value, dose.get("food_instruction", ""), dose.get("status", "Pending")))
    connection.commit()
    connection.close()
    return True


def get_todays_medicines():
    connection = get_connection()
    rows = connection.execute("SELECT * FROM medication_schedule WHERE date=? ORDER BY time ASC", (str(date.today()),)).fetchall()
    connection.close()
    return rows


def get_medication_history():
    connection = get_connection()
    rows = connection.execute("SELECT * FROM medication_schedule ORDER BY date DESC, time DESC").fetchall()
    connection.close()
    return rows


def get_saved_prescriptions():
    connection = get_connection()
    rows = connection.execute('''
        SELECT schedule_group_id, medicine_name, dosage,
               MIN(date) AS start_date, MAX(date) AS end_date, COUNT(*) AS total_doses
        FROM medication_schedule
        GROUP BY schedule_group_id, medicine_name, dosage
        ORDER BY start_date DESC
    ''').fetchall()
    connection.close()
    return rows


def delete_prescription(schedule_group_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM medication_schedule WHERE schedule_group_id=?", (schedule_group_id,))
    deleted = cursor.rowcount
    connection.commit()
    connection.close()
    return deleted


def update_medication_status(medication_id, new_status):
    connection = get_connection()
    connection.execute("UPDATE medication_schedule SET status=? WHERE id=?", (new_status, medication_id))
    connection.commit()
    connection.close()


def get_medication_summary():
    connection = get_connection()
    row = connection.execute('''
        SELECT COUNT(*) AS total_doses,
               SUM(CASE WHEN status='Taken' THEN 1 ELSE 0 END) AS taken_doses,
               SUM(CASE WHEN status='Skipped' THEN 1 ELSE 0 END) AS skipped_doses,
               SUM(CASE WHEN status='Missed' THEN 1 ELSE 0 END) AS missed_doses,
               SUM(CASE WHEN status='Snoozed' THEN 1 ELSE 0 END) AS snoozed_doses
        FROM medication_schedule
    ''').fetchone()
    connection.close()
    return row


def get_patient_code(user_id):
    connection = get_connection()
    row = connection.execute("SELECT patient_code FROM patient_profile WHERE user_id=?", (user_id,)).fetchone()
    connection.close()
    return row["patient_code"] if row and row["patient_code"] else f"PAT-{int(user_id):05d}"


def get_patient_profile(user_id):
    connection = get_connection()
    row = connection.execute("SELECT * FROM patient_profile WHERE user_id=?", (user_id,)).fetchone()
    connection.close()
    return row


def save_patient_profile(user_id, full_name, age, gender, blood_group, emergency_contact, allergies, medical_conditions, doctor_name, doctor_contact, additional_notes):
    connection = get_connection()
    connection.execute('''
        INSERT INTO patient_profile
        (user_id, patient_code, full_name, age, gender, blood_group, emergency_contact, allergies,
         medical_conditions, doctor_name, doctor_contact, additional_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            patient_code=COALESCE(patient_profile.patient_code, excluded.patient_code),
            full_name=excluded.full_name, age=excluded.age, gender=excluded.gender,
            blood_group=excluded.blood_group, emergency_contact=excluded.emergency_contact,
            allergies=excluded.allergies, medical_conditions=excluded.medical_conditions,
            doctor_name=excluded.doctor_name, doctor_contact=excluded.doctor_contact,
            additional_notes=excluded.additional_notes, updated_at=CURRENT_TIMESTAMP
    ''', (user_id, f"PAT-{int(user_id):05d}", full_name, age, gender, blood_group, emergency_contact, allergies, medical_conditions, doctor_name, doctor_contact, additional_notes))
    connection.commit()
    connection.close()
    return True


def delete_patient_data(user_id):
    """Delete all local profile and medicine data belonging to a patient."""
    connection = get_connection()
    try:
        connection.execute("DELETE FROM medication_schedule WHERE patient_user_id=?", (user_id,))
        connection.execute("DELETE FROM patient_profile WHERE user_id=?", (user_id,))
        connection.commit()
    finally:
        connection.close()
