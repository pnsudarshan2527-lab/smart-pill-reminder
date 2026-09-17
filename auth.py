import sqlite3
import hashlib
from pathlib import Path

AUTH_DB = Path(__file__).parent / 'auth.db'

def get_auth_connection():
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(str(password).encode('utf-8')).hexdigest()

def initialize_auth_database():
    conn = get_auth_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Patient',
        caregiver_id INTEGER,
        relationship TEXT DEFAULT 'Self',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def register_user(full_name, username, password, role='Patient'):
    full_name, username = str(full_name).strip(), str(username).strip().lower()
    role = str(role).strip().title()
    if not full_name or not username or not password:
        return False, 'All fields are required.'
    if len(password) < 4:
        return False, 'Password must contain at least 4 characters.'
    conn = get_auth_connection()
    try:
        conn.execute('INSERT INTO users (full_name, username, password, role) VALUES (?, ?, ?, ?)',
                     (full_name, username, hash_password(password), role))
        conn.commit()
        return True, 'Registration successful.'
    except sqlite3.IntegrityError:
        return False, 'Username already exists.'
    except Exception as e:
        return False, f'Registration error: {e}'
    finally:
        conn.close()

def register_patient(caregiver_id, full_name, username, password, relationship='Patient'):
    full_name, username = str(full_name).strip(), str(username).strip().lower()
    conn = get_auth_connection()
    try:
        conn.execute('''INSERT INTO users
            (full_name, username, password, role, caregiver_id, relationship)
            VALUES (?, ?, ?, 'Patient', ?, ?)''',
            (full_name, username, hash_password(password), caregiver_id, relationship))
        conn.commit()
        return True, 'Patient registered successfully.', {'id': conn.execute('SELECT last_insert_rowid()').fetchone()[0]}
    except sqlite3.IntegrityError:
        return False, 'Username already exists.', None
    except Exception as e:
        return False, f'Patient registration error: {e}', None
    finally:
        conn.close()

def login_user(username, password):
    conn = get_auth_connection()
    try:
        user = conn.execute('SELECT id, full_name, username, password, role, caregiver_id, relationship FROM users WHERE username = ?',
                            (str(username).strip().lower(),)).fetchone()
        if user is None or user['password'] != hash_password(password):
            return False, 'Invalid username or password.', None
        return True, 'Login successful.', {
            'id': user['id'], 'full_name': user['full_name'], 'username': user['username'],
            'role': user['role'], 'caregiver_id': user['caregiver_id'], 'relationship': user['relationship']
        }
    except Exception as e:
        return False, f'Login error: {e}', None
    finally:
        conn.close()

def get_caregiver_patients(caregiver_id):
    conn = get_auth_connection()
    try:
        rows = conn.execute('SELECT * FROM users WHERE caregiver_id = ? AND role = "Patient" ORDER BY full_name', (caregiver_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def check_patient_access(caregiver_id, patient_id):
    conn = get_auth_connection()
    try:
        return conn.execute('SELECT 1 FROM users WHERE id = ? AND caregiver_id = ?', (patient_id, caregiver_id)).fetchone() is not None
    finally:
        conn.close()


def delete_patient(caregiver_id, patient_id):
    """Delete a patient only if they belong to the logged-in caregiver."""
    conn = get_auth_connection()
    try:
        row = conn.execute(
            "SELECT id, full_name FROM users WHERE id = ? AND caregiver_id = ? AND role = 'Patient'",
            (patient_id, caregiver_id)
        ).fetchone()
        if row is None:
            return False, "Patient not found or access denied."
        conn.execute("DELETE FROM users WHERE id = ? AND caregiver_id = ? AND role = 'Patient'",
                     (patient_id, caregiver_id))
        conn.commit()
        return True, f"Patient account '{row['full_name']}' deleted successfully."
    except Exception as e:
        return False, f"Delete error: {e}"
    finally:
        conn.close()
