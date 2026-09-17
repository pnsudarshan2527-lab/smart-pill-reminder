import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4


# medication.db will be created in the same folder as database.py
DATABASE_NAME = Path(__file__).resolve().parent / "medication.db"


def get_connection():
    """
    Create a database connection.
    """

    connection = sqlite3.connect(
        DATABASE_NAME,
        check_same_thread=False,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    # Enable foreign key support
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database():
    """
    Create required tables and add missing columns
    when upgrading an older database.
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # -------------------------------------------------
        # Medication schedule table
        # -------------------------------------------------
        cursor.execute(
            """
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
            """
        )

        # -------------------------------------------------
        # Patient profile table
        # -------------------------------------------------
        cursor.execute(
            """
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
            """
        )

        # -------------------------------------------------
        # Add missing columns to old medication table
        # -------------------------------------------------
        cursor.execute(
            "PRAGMA table_info(medication_schedule)"
        )

        medication_columns = {
            row["name"] for row in cursor.fetchall()
        }

        if "patient_user_id" not in medication_columns:
            cursor.execute(
                """
                ALTER TABLE medication_schedule
                ADD COLUMN patient_user_id INTEGER
                """
            )

        if "schedule_group_id" not in medication_columns:
            cursor.execute(
                """
                ALTER TABLE medication_schedule
                ADD COLUMN schedule_group_id TEXT
                """
            )

        # -------------------------------------------------
        # Add missing columns to old patient profile table
        # -------------------------------------------------
        cursor.execute(
            "PRAGMA table_info(patient_profile)"
        )

        profile_columns = {
            row["name"] for row in cursor.fetchall()
        }

        if "patient_code" not in profile_columns:
            cursor.execute(
                """
                ALTER TABLE patient_profile
                ADD COLUMN patient_code TEXT
                """
            )

        # -------------------------------------------------
        # Generate patient codes for old profiles
        # -------------------------------------------------
        cursor.execute(
            """
            SELECT id, user_id
            FROM patient_profile
            WHERE patient_code IS NULL
            OR patient_code = ''
            """
        )

        old_profiles = cursor.fetchall()

        for row in old_profiles:
            patient_code = f"PAT-{int(row['user_id']):05d}"

            cursor.execute(
                """
                UPDATE patient_profile
                SET patient_code = ?
                WHERE id = ?
                """,
                (
                    patient_code,
                    row["id"]
                )
            )

        # -------------------------------------------------
        # Generate schedule group IDs for old medicines
        # -------------------------------------------------
        cursor.execute(
            """
            SELECT id
            FROM medication_schedule
            WHERE schedule_group_id IS NULL
            OR schedule_group_id = ''
            """
        )

        old_schedules = cursor.fetchall()

        for row in old_schedules:
            cursor.execute(
                """
                UPDATE medication_schedule
                SET schedule_group_id = ?
                WHERE id = ?
                """,
                (
                    str(uuid4()),
                    row["id"]
                )
            )

        # -------------------------------------------------
        # Helpful indexes for faster searches
        # -------------------------------------------------
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_medication_patient_date
            ON medication_schedule(patient_user_id, date)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_medication_schedule_group
            ON medication_schedule(schedule_group_id)
            """
        )

        connection.commit()

    finally:
        connection.close()


def save_schedule(schedule):
    """
    Save all doses belonging to one medicine schedule.

    Each item in schedule should contain:
        patient_user_id
        medicine_name
        dosage
        date
        time
        food_instruction
        status
    """

    if not schedule:
        return False

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Use existing group ID or create a new one
        group_id = (
            schedule[0].get("schedule_group_id")
            or str(uuid4())
        )

        # Add the same group ID to every dose
        for dose in schedule:
            dose["schedule_group_id"] = group_id

        # Prevent duplicate schedule insertion
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM medication_schedule
            WHERE schedule_group_id = ?
            """,
            (group_id,)
        )

        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            return False

        for dose in schedule:
            dose_time = dose["time"]

            if hasattr(dose_time, "strftime"):
                time_value = dose_time.strftime("%H:%M:%S")
            else:
                time_value = str(dose_time)

            dose_date = dose["date"]

            if hasattr(dose_date, "strftime"):
                date_value = dose_date.strftime("%Y-%m-%d")
            else:
                date_value = str(dose_date)

            patient_user_id = dose.get("patient_user_id")

            cursor.execute(
                """
                INSERT INTO medication_schedule
                (
                    schedule_group_id,
                    patient_user_id,
                    medicine_name,
                    dosage,
                    date,
                    time,
                    food_instruction,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    patient_user_id,
                    dose["medicine_name"],
                    dose["dosage"],
                    date_value,
                    time_value,
                    dose.get("food_instruction", ""),
                    dose.get("status", "Pending")
                )
            )

        connection.commit()
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_todays_medicines(
    patient_id=None,
    caregiver_id=None
):
    """
    Get today's medicines.

    For a patient:
        get_todays_medicines(patient_id=logged_in_patient_id)

    If patient_id is None, all today's medicines are returned.
    """

    connection = get_connection()

    try:
        query = """
            SELECT *
            FROM medication_schedule
            WHERE date = ?
        """

        params = [str(date.today())]

        if patient_id is not None:
            query += """
                AND patient_user_id = ?
            """
            params.append(int(patient_id))

        query += """
            ORDER BY time ASC, id ASC
        """

        rows = connection.execute(
            query,
            params
        ).fetchall()

        return rows

    finally:
        connection.close()


def get_medicines_for_date(
    selected_date,
    patient_id=None
):
    """
    Get medicines for a specific date.
    """

    connection = get_connection()

    try:
        if hasattr(selected_date, "strftime"):
            selected_date = selected_date.strftime("%Y-%m-%d")
        else:
            selected_date = str(selected_date)

        query = """
            SELECT *
            FROM medication_schedule
            WHERE date = ?
        """

        params = [selected_date]

        if patient_id is not None:
            query += """
                AND patient_user_id = ?
            """
            params.append(int(patient_id))

        query += """
            ORDER BY time ASC, id ASC
        """

        rows = connection.execute(
            query,
            params
        ).fetchall()

        return rows

    finally:
        connection.close()


def get_medication_history(
    patient_id=None,
    caregiver_id=None
):
    """
    Get medication history.
    """

    connection = get_connection()

    try:
        query = """
            SELECT *
            FROM medication_schedule
        """

        params = []

        if patient_id is not None:
            query += """
                WHERE patient_user_id = ?
            """
            params.append(int(patient_id))

        query += """
            ORDER BY date DESC, time DESC, id DESC
        """

        rows = connection.execute(
            query,
            params
        ).fetchall()

        return rows

    finally:
        connection.close()


def get_saved_prescriptions(
    patient_id=None,
    caregiver_id=None
):
    """
    Get saved prescriptions grouped by schedule_group_id.
    """

    connection = get_connection()

    try:
        query = """
            SELECT
                schedule_group_id,
                patient_user_id,
                medicine_name,
                dosage,
                MIN(date) AS start_date,
                MAX(date) AS end_date,
                COUNT(*) AS total_doses
            FROM medication_schedule
        """

        params = []

        if patient_id is not None:
            query += """
                WHERE patient_user_id = ?
            """
            params.append(int(patient_id))

        query += """
            GROUP BY
                schedule_group_id,
                patient_user_id,
                medicine_name,
                dosage
            ORDER BY start_date DESC
        """

        rows = connection.execute(
            query,
            params
        ).fetchall()

        return rows

    finally:
        connection.close()


def delete_prescription(schedule_group_id):
    """
    Delete all doses belonging to one prescription.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM medication_schedule
            WHERE schedule_group_id = ?
            """,
            (schedule_group_id,)
        )

        deleted_count = cursor.rowcount

        connection.commit()

        return deleted_count

    finally:
        connection.close()


def update_medication_status(
    medication_id,
    new_status
):
    """
    Update medicine status.

    Allowed examples:
        Pending
        Taken
        Skipped
        Snoozed
        Missed
    """

    allowed_statuses = {
        "Pending",
        "Taken",
        "Skipped",
        "Snoozed",
        "Missed"
    }

    if new_status not in allowed_statuses:
        return False

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE medication_schedule
            SET status = ?
            WHERE id = ?
            """,
            (
                new_status,
                int(medication_id)
            )
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


def get_medication_summary(
    patient_id=None,
    caregiver_id=None
):
    """
    Get medication summary for a patient.
    """

    connection = get_connection()

    try:
        query = """
            SELECT
                COUNT(*) AS total_doses,

                SUM(
                    CASE
                        WHEN status = 'Taken'
                        THEN 1
                        ELSE 0
                    END
                ) AS taken_doses,

                SUM(
                    CASE
                        WHEN status = 'Skipped'
                        THEN 1
                        ELSE 0
                    END
                ) AS skipped_doses,

                SUM(
                    CASE
                        WHEN status = 'Missed'
                        THEN 1
                        ELSE 0
                    END
                ) AS missed_doses,

                SUM(
                    CASE
                        WHEN status = 'Snoozed'
                        THEN 1
                        ELSE 0
                    END
                ) AS snoozed_doses

            FROM medication_schedule
        """

        params = []

        if patient_id is not None:
            query += """
                WHERE patient_user_id = ?
            """
            params.append(int(patient_id))

        row = connection.execute(
            query,
            params
        ).fetchone()

        return row

    finally:
        connection.close()


def get_patient_code(user_id):
    """
    Get the patient's code.
    """

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT patient_code
            FROM patient_profile
            WHERE user_id = ?
            """,
            (int(user_id),)
        ).fetchone()

        if row and row["patient_code"]:
            return row["patient_code"]

        return f"PAT-{int(user_id):05d}"

    finally:
        connection.close()


def get_patient_profile(user_id):
    """
    Get a patient's profile.
    """

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM patient_profile
            WHERE user_id = ?
            """,
            (int(user_id),)
        ).fetchone()

        return row

    finally:
        connection.close()


def save_patient_profile(
    user_id,
    full_name,
    age,
    gender,
    blood_group,
    emergency_contact,
    allergies,
    medical_conditions,
    doctor_name,
    doctor_contact,
    additional_notes
):
    """
    Create or update a patient profile.
    """

    connection = get_connection()

    try:
        patient_code = f"PAT-{int(user_id):05d}"

        connection.execute(
            """
            INSERT INTO patient_profile
            (
                user_id,
                patient_code,
                full_name,
                age,
                gender,
                blood_group,
                emergency_contact,
                allergies,
                medical_conditions,
                doctor_name,
                doctor_contact,
                additional_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                patient_code = COALESCE(
                    patient_profile.patient_code,
                    excluded.patient_code
                ),
                full_name = excluded.full_name,
                age = excluded.age,
                gender = excluded.gender,
                blood_group = excluded.blood_group,
                emergency_contact = excluded.emergency_contact,
                allergies = excluded.allergies,
                medical_conditions = excluded.medical_conditions,
                doctor_name = excluded.doctor_name,
                doctor_contact = excluded.doctor_contact,
                additional_notes = excluded.additional_notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(user_id),
                patient_code,
                full_name,
                age,
                gender,
                blood_group,
                emergency_contact,
                allergies,
                medical_conditions,
                doctor_name,
                doctor_contact,
                additional_notes
            )
        )

        connection.commit()

        return True

    finally:
        connection.close()


def delete_patient_data(user_id):
    """
    Delete all medication and profile data for a patient.
    """

    connection = get_connection()

    try:
        connection.execute(
            """
            DELETE FROM medication_schedule
            WHERE patient_user_id = ?
            """,
            (int(user_id),)
        )

        connection.execute(
            """
            DELETE FROM patient_profile
            WHERE user_id = ?
            """,
            (int(user_id),)
        )

        connection.commit()

        return True

    finally:
        connection.close()


def get_all_schedule_records():
    """
    Debug helper:
    Return all medicine records from the database.
    """

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM medication_schedule
            ORDER BY date DESC, time DESC, id DESC
            """
        ).fetchall()

        return rows

    finally:
        connection.close()


def get_patient_schedule_count(patient_id):
    """
    Return the number of medicine records for one patient.
    """

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM medication_schedule
            WHERE patient_user_id = ?
            """,
            (int(patient_id),)
        ).fetchone()

        return row["total"]

    finally:
        connection.close()
