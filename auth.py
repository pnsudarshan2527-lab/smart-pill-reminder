import sqlite3
import hashlib
from pathlib import Path


# Keep auth.db in the same folder as this file
AUTH_DB = Path(__file__).resolve().parent / "auth.db"


def get_auth_connection():
    """
    Create and return a connection to the authentication database.
    """
    conn = sqlite3.connect(
        AUTH_DB,
        check_same_thread=False,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    # Enable foreign key support
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def hash_password(password):
    """
    Convert password into a SHA-256 hash.
    """
    return hashlib.sha256(
        str(password).encode("utf-8")
    ).hexdigest()


def initialize_auth_database():
    """
    Create the users table if it does not already exist.
    """
    conn = get_auth_connection()

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Patient',
                caregiver_id INTEGER,
                relationship TEXT DEFAULT 'Self',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.commit()

    finally:
        conn.close()


def register_user(
    full_name,
    username,
    password,
    role="Patient"
):
    """
    Register a normal user.

    This is mainly used for registering:
    - Caregiver
    - Patient
    """

    full_name = str(full_name).strip()
    username = str(username).strip().lower()
    password = str(password)
    role = str(role).strip().title()

    if not full_name or not username or not password:
        return False, "All fields are required."

    if len(password) < 4:
        return False, "Password must contain at least 4 characters."

    allowed_roles = {"Patient", "Caregiver"}

    if role not in allowed_roles:
        return False, "Invalid user role."

    conn = get_auth_connection()

    try:
        conn.execute(
            """
            INSERT INTO users
            (
                full_name,
                username,
                password,
                role,
                caregiver_id,
                relationship
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                full_name,
                username,
                hash_password(password),
                role,
                None,
                "Self"
            )
        )

        conn.commit()

        return True, "Registration successful."

    except sqlite3.IntegrityError:
        return False, "Username already exists."

    except Exception as error:
        return False, f"Registration error: {error}"

    finally:
        conn.close()


def register_patient(
    caregiver_id,
    full_name,
    username,
    password,
    relationship="Patient"
):
    """
    Register a patient under a specific caregiver.
    """

    full_name = str(full_name).strip()
    username = str(username).strip().lower()
    password = str(password).strip()
    relationship = str(relationship).strip() or "Patient"

    if not full_name or not username or not password:
        return False, "All fields are required.", None

    if len(password) < 4:
        return False, "Password must contain at least 4 characters.", None

    if caregiver_id is None:
        return False, "Caregiver ID is required.", None

    conn = get_auth_connection()

    try:
        # Verify that the caregiver exists
        caregiver = conn.execute(
            """
            SELECT id
            FROM users
            WHERE id = ?
            AND role = 'Caregiver'
            """,
            (caregiver_id,)
        ).fetchone()

        if caregiver is None:
            return False, "Invalid caregiver account.", None

        cursor = conn.execute(
            """
            INSERT INTO users
            (
                full_name,
                username,
                password,
                role,
                caregiver_id,
                relationship
            )
            VALUES (?, ?, ?, 'Patient', ?, ?)
            """,
            (
                full_name,
                username,
                hash_password(password),
                caregiver_id,
                relationship
            )
        )

        patient_id = cursor.lastrowid

        conn.commit()

        return (
            True,
            "Patient registered successfully.",
            {
                "id": patient_id,
                "full_name": full_name,
                "username": username,
                "role": "Patient",
                "caregiver_id": caregiver_id,
                "relationship": relationship
            }
        )

    except sqlite3.IntegrityError:
        return False, "Username already exists.", None

    except Exception as error:
        return False, f"Patient registration error: {error}", None

    finally:
        conn.close()


def login_user(username, password):
    """
    Authenticate a user and return user details.
    """

    username = str(username).strip().lower()
    password = str(password)

    if not username or not password:
        return False, "Username and password are required.", None

    conn = get_auth_connection()

    try:
        user = conn.execute(
            """
            SELECT
                id,
                full_name,
                username,
                password,
                role,
                caregiver_id,
                relationship
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if user is None:
            return False, "Invalid username or password.", None

        stored_password = user["password"]
        entered_password = hash_password(password)

        if stored_password != entered_password:
            return False, "Invalid username or password.", None

        user_data = {
            "id": user["id"],
            "full_name": user["full_name"],
            "username": user["username"],
            "role": user["role"],
            "caregiver_id": user["caregiver_id"],
            "relationship": user["relationship"]
        }

        return True, "Login successful.", user_data

    except Exception as error:
        return False, f"Login error: {error}", None

    finally:
        conn.close()


def get_user_by_id(user_id):
    """
    Get one user using their ID.
    """

    conn = get_auth_connection()

    try:
        row = conn.execute(
            """
            SELECT
                id,
                full_name,
                username,
                role,
                caregiver_id,
                relationship,
                created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def get_user_by_username(username):
    """
    Get one user using their username.
    """

    username = str(username).strip().lower()

    conn = get_auth_connection()

    try:
        row = conn.execute(
            """
            SELECT
                id,
                full_name,
                username,
                role,
                caregiver_id,
                relationship,
                created_at
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def get_caregiver_patients(caregiver_id):
    """
    Return all patients registered under a caregiver.
    """

    conn = get_auth_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                id,
                full_name,
                username,
                role,
                caregiver_id,
                relationship,
                created_at
            FROM users
            WHERE caregiver_id = ?
            AND role = 'Patient'
            ORDER BY full_name ASC
            """,
            (caregiver_id,)
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def check_patient_access(caregiver_id, patient_id):
    """
    Check whether a patient belongs to a caregiver.
    """

    conn = get_auth_connection()

    try:
        row = conn.execute(
            """
            SELECT id
            FROM users
            WHERE id = ?
            AND caregiver_id = ?
            AND role = 'Patient'
            """,
            (patient_id, caregiver_id)
        ).fetchone()

        return row is not None

    finally:
        conn.close()


def check_caregiver_access(caregiver_id):
    """
    Check whether the user is a valid caregiver.
    """

    conn = get_auth_connection()

    try:
        row = conn.execute(
            """
            SELECT id
            FROM users
            WHERE id = ?
            AND role = 'Caregiver'
            """,
            (caregiver_id,)
        ).fetchone()

        return row is not None

    finally:
        conn.close()


def update_patient_relationship(
    caregiver_id,
    patient_id,
    relationship
):
    """
    Update the relationship between caregiver and patient.
    """

    relationship = str(relationship).strip()

    if not relationship:
        return False, "Relationship is required."

    if not check_patient_access(caregiver_id, patient_id):
        return False, "Patient not found or access denied."

    conn = get_auth_connection()

    try:
        conn.execute(
            """
            UPDATE users
            SET relationship = ?
            WHERE id = ?
            AND caregiver_id = ?
            AND role = 'Patient'
            """,
            (
                relationship,
                patient_id,
                caregiver_id
            )
        )

        conn.commit()

        return True, "Patient relationship updated successfully."

    except Exception as error:
        return False, f"Update error: {error}"

    finally:
        conn.close()


def delete_patient(caregiver_id, patient_id):
    """
    Delete a patient only if the patient belongs to the caregiver.
    """

    conn = get_auth_connection()

    try:
        patient = conn.execute(
            """
            SELECT id, full_name
            FROM users
            WHERE id = ?
            AND caregiver_id = ?
            AND role = 'Patient'
            """,
            (
                patient_id,
                caregiver_id
            )
        ).fetchone()

        if patient is None:
            return False, "Patient not found or access denied."

        conn.execute(
            """
            DELETE FROM users
            WHERE id = ?
            AND caregiver_id = ?
            AND role = 'Patient'
            """,
            (
                patient_id,
                caregiver_id
            )
        )

        conn.commit()

        return (
            True,
            f"Patient account '{patient['full_name']}' deleted successfully."
        )

    except Exception as error:
        return False, f"Delete error: {error}"

    finally:
        conn.close()


def delete_user(user_id):
    """
    Delete a user by ID.
    Use this carefully.
    """

    conn = get_auth_connection()

    try:
        conn.execute(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            (user_id,)
        )

        conn.commit()

        return True, "User deleted successfully."

    except Exception as error:
        return False, f"Delete error: {error}"

    finally:
        conn.close()
