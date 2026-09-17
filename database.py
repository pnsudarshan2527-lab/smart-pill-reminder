import sqlite3

from datetime import date
from uuid import uuid4


# ==================================================
# DATABASE CONFIGURATION
# ==================================================

DATABASE_NAME = "medication.db"


# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_NAME,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


# ==================================================
# INITIALIZE DATABASE
# ==================================================

def initialize_database():

    connection = get_connection()

    cursor = connection.cursor()

    # Create the table if it does not exist.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS medication_schedule (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            schedule_group_id TEXT,

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

    connection.commit()

    # ==================================================
    # DATABASE MIGRATION
    # ==================================================
    #
    # If the table was created using the old version,
    # schedule_group_id will not exist.
    #
    # This checks the existing columns and adds the
    # missing column without deleting old records.
    # ==================================================

    cursor.execute(
        """
        PRAGMA table_info(medication_schedule)
        """
    )

    existing_columns = [
        column["name"]
        for column in cursor.fetchall()
    ]

    if "schedule_group_id" not in existing_columns:

        cursor.execute(
            """
            ALTER TABLE medication_schedule
            ADD COLUMN schedule_group_id TEXT
            """
        )

    connection.commit()

    # ==================================================
    # MIGRATE OLD RECORDS
    # ==================================================
    #
    # Old records do not have schedule_group_id.
    # Give each old medicine row its own group ID.
    # This keeps old data usable.
    # ==================================================

    cursor.execute(
        """
        SELECT id
        FROM medication_schedule
        WHERE schedule_group_id IS NULL
        """
    )

    old_records = cursor.fetchall()

    for record in old_records:

        cursor.execute(
            """
            UPDATE medication_schedule
            SET schedule_group_id = ?
            WHERE id = ?
            """,
            (
                str(uuid4()),
                record["id"]
            )
        )

    connection.commit()

    connection.close()


# ==================================================
# SAVE SCHEDULE
# ==================================================

def save_schedule(schedule):

    if not schedule:

        return False

    connection = get_connection()

    cursor = connection.cursor()

    # Get the group ID of this prescription.
    schedule_group_id = schedule[0].get(
        "schedule_group_id"
    )

    # If the scheduler did not provide a group ID,
    # create one.
    if not schedule_group_id:

        schedule_group_id = str(uuid4())

        for dose in schedule:

            dose["schedule_group_id"] = (
                schedule_group_id
            )

    # ==================================================
    # DUPLICATE CHECK
    # ==================================================
    #
    # If this exact prescription group already exists,
    # do not insert it again.
    # ==================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM medication_schedule
        WHERE schedule_group_id = ?
        """,
        (
            schedule_group_id,
        )
    )

    existing_count = cursor.fetchone()[0]

    if existing_count > 0:

        connection.close()

        return False

    # ==================================================
    # INSERT NEW SCHEDULE
    # ==================================================

    for dose in schedule:

        cursor.execute(
            """
            INSERT INTO medication_schedule
            (
                schedule_group_id,
                medicine_name,
                dosage,
                date,
                time,
                food_instruction,
                status
            )

            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dose["schedule_group_id"],
                dose["medicine_name"],
                dose["dosage"],
                str(dose["date"]),
                dose["time"].strftime("%H:%M:%S"),
                dose["food_instruction"],
                dose["status"]
            )
        )

    connection.commit()

    connection.close()

    return True


# ==================================================
# GET TODAY'S MEDICINES
# ==================================================

def get_todays_medicines():

    connection = get_connection()

    cursor = connection.cursor()

    today = str(date.today())

    cursor.execute(
        """
        SELECT *
        FROM medication_schedule
        WHERE date = ?
        ORDER BY time ASC
        """,
        (
            today,
        )
    )

    medicines = cursor.fetchall()

    connection.close()

    return medicines


# ==================================================
# GET MEDICATION HISTORY
# ==================================================

def get_medication_history():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM medication_schedule
        ORDER BY date DESC, time DESC
        """
    )

    history = cursor.fetchall()

    connection.close()

    return history


# ==================================================
# GET SAVED PRESCRIPTIONS
# ==================================================

def get_saved_prescriptions():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            schedule_group_id,
            medicine_name,
            dosage,
            MIN(date) AS start_date,
            MAX(date) AS end_date,
            COUNT(*) AS total_doses

        FROM medication_schedule

        GROUP BY
            schedule_group_id,
            medicine_name,
            dosage

        ORDER BY start_date DESC
        """
    )

    prescriptions = cursor.fetchall()

    connection.close()

    return prescriptions


# ==================================================
# DELETE PRESCRIPTION
# ==================================================

def delete_prescription(schedule_group_id):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM medication_schedule
        WHERE schedule_group_id = ?
        """,
        (
            schedule_group_id,
        )
    )

    deleted_rows = cursor.rowcount

    connection.commit()

    connection.close()

    return deleted_rows


# ==================================================
# UPDATE MEDICATION STATUS
# ==================================================

def update_medication_status(
    medication_id,
    new_status
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE medication_schedule
        SET status = ?
        WHERE id = ?
        """,
        (
            new_status,
            medication_id
        )
    )

    connection.commit()

    connection.close()


# ==================================================
# GET MEDICATION SUMMARY
# ==================================================

def get_medication_summary():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
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
    )

    summary = cursor.fetchone()

    connection.close()

    return summary