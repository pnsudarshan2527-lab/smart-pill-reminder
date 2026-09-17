import streamlit as st
import streamlit.components.v1 as components
import base64
import io
import wave
import math

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

from datetime import date, time, datetime

from scheduler import generate_schedule

from database import (
    initialize_database,
    save_schedule,
    get_todays_medicines,
    get_medication_history,
    get_saved_prescriptions,
    delete_prescription,
    update_medication_status,
    get_medication_summary,
    get_patient_profile,
    save_patient_profile,
    get_patient_code,
    delete_patient_data
)

from auth import (
    initialize_auth_database,
    register_user,
    login_user,
    register_patient,
    get_caregiver_patients,
    delete_patient
)

# ==================================================
# ALARM SOUND HELPER
# ==================================================

def render_alarm_sound():
    """
    Browser-safe alarm.
    User must click Start Alarm because browsers block automatic sound.
    """

    components.html(
        """
        <div style="font-family:Arial; padding:12px; border:1px solid #ef4444;
                    border-radius:10px; background:#fff1f2;">

            <h3 style="color:#b91c1c;">🔔 Medicine Alarm</h3>

            <p style="color:#7f1d1d;">
                Click the button below to start the alarm sound.
            </p>

            <button id="startAlarm"
                    style="background:#dc2626;color:white;border:none;
                           padding:12px 20px;border-radius:8px;
                           font-size:16px;cursor:pointer;">
                🔊 Start Alarm
            </button>

            <button id="stopAlarm"
                    style="background:#374151;color:white;border:none;
                           padding:12px 20px;border-radius:8px;
                           font-size:16px;cursor:pointer;margin-left:8px;">
                🔇 Stop Alarm
            </button>

            <p id="alarmStatus" style="font-weight:bold;"></p>

            <script>
                let audioContext = null;
                let alarmTimer = null;

                function beep() {
                    if (!audioContext) {
                        audioContext = new (
                            window.AudioContext ||
                            window.webkitAudioContext
                        )();
                    }

                    const oscillator = audioContext.createOscillator();
                    const gainNode = audioContext.createGain();

                    oscillator.type = "square";
                    oscillator.frequency.setValueAtTime(
                        880,
                        audioContext.currentTime
                    );

                    gainNode.gain.setValueAtTime(
                        0.25,
                        audioContext.currentTime
                    );

                    oscillator.connect(gainNode);
                    gainNode.connect(audioContext.destination);

                    oscillator.start();

                    oscillator.stop(
                        audioContext.currentTime + 0.35
                    );
                }

                document.getElementById("startAlarm")
                    .addEventListener("click", async function() {
                        if (!audioContext) {
                            audioContext = new (
                                window.AudioContext ||
                                window.webkitAudioContext
                            )();
                        }

                        if (audioContext.state === "suspended") {
                            await audioContext.resume();
                        }

                        if (!alarmTimer) {
                            beep();
                            alarmTimer = setInterval(beep, 1000);
                        }

                        document.getElementById("alarmStatus").innerText =
                            "Alarm is ringing.";
                    });

                document.getElementById("stopAlarm")
                    .addEventListener("click", function() {
                        if (alarmTimer) {
                            clearInterval(alarmTimer);
                            alarmTimer = null;
                        }

                        document.getElementById("alarmStatus").innerText =
                            "Alarm stopped.";
                    });
            </script>
        </div>
        """,
        height=230
    )


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Smart Pill Reminder",
    page_icon="💊",
    layout="wide"
)
# ==================================================
# INITIALIZE DATABASES
# ==================================================

initialize_database()
initialize_auth_database()


# ==================================================
# HELPER FUNCTION
# ==================================================

def convert_to_24_hour(
    selected_hour,
    selected_minute,
    selected_period
):
    """
    Convert 12-hour time with AM/PM
    into Python time object.
    """

    if selected_period == "AM":

        converted_hour = (
            0 if selected_hour == 12 else selected_hour
        )

    else:

        converted_hour = (
            12
            if selected_hour == 12
            else selected_hour + 12
        )

    return time(
        converted_hour,
        selected_minute
    )


# ==================================================
# SESSION STATE
# ==================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None


# ==================================================
# LOGIN / REGISTRATION SCREEN
# ==================================================

if not st.session_state.logged_in:

    st.title("💊 Smart Pill Reminder")

    st.write("Please login or create an account to continue.")

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:

        st.subheader("Login")

        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", type="primary", key="login_button"):

            success, message, user_data = login_user(
                login_username,
                login_password
            )

            if success:
                st.session_state.logged_in = True
                st.session_state.user = user_data
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with register_tab:

        st.subheader("Create New Account")

        register_full_name = st.text_input("Full Name", key="register_full_name")
        register_username = st.text_input("Create Username", key="register_username")
        register_password = st.text_input("Create Password", type="password", key="register_password")
        register_confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm_password")

        register_role = st.selectbox(
            "Account Type",
            ["Patient", "Caregiver"],
            key="register_role"
        )

        if st.button("Register", type="primary", key="register_button"):

            if register_password != register_confirm_password:
                st.error("Passwords do not match.")
            else:
                success, message = register_user(
                    full_name=register_full_name,
                    username=register_username,
                    password=register_password,
                    role=register_role
                )

                if success:
                    st.success(message)
                    st.info("Open the Login tab and login using your new account.")
                else:
                    st.error(message)

    st.stop()


# ==================================================
# SIDEBAR USER INFORMATION AND NAVIGATION
# ==================================================

st.sidebar.title("💊 Smart Pill Reminder")

st.sidebar.success(
    f"Logged in as: {st.session_state.user['full_name']}"
)

st.sidebar.write(
    f"Role: {st.session_state.user['role']}"
)

if st.sidebar.button("Logout", key="logout_button"):

    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()


user_role = st.session_state.user["role"]

if user_role == "Caregiver":
    navigation_options = [
        "Dashboard",
        "Patient & Medicines",
        "Saved Prescriptions",
        "Today's Medicines",
        "Medication History",
        "Caregiver Dashboard"
    ]
else:
    navigation_options = [
        "Dashboard",
        "Patient & Medicines",
        "Today's Medicines",
        "Medicine Alarm",
        "Medicine Chatbot",
        "Medication History"
    ]

page = st.sidebar.radio("Navigation", navigation_options)


# ==================================================
# MERGED PATIENT ID + PATIENT DETAILS + MEDICINE DETAILS
# ==================================================

if page == "Patient & Medicines":
    st.title("💊 Patient & Medicines")
    st.caption("Create/select a Patient ID and save patient details with multiple medicines in one form.")

    patients = get_caregiver_patients(st.session_state.user["id"])
    create_col, select_col = st.columns([1, 2])

    with create_col:
        st.subheader("Create Patient ID")
        with st.form("create_patient_id_form"):
            new_patient_name = st.text_input("Patient name")
            new_patient_username = st.text_input(
                "Patient username",
                placeholder="Example: rahul123"
            )
            new_patient_password = st.text_input(
                "Patient password",
                type="password",
                placeholder="Minimum 4 characters"
            )
            create_patient_button = st.form_submit_button(
                "➕ Create Patient ID"
            )

        if create_patient_button:
            if not new_patient_name.strip():
                st.error("Enter the patient name.")
            elif not new_patient_username.strip():
                st.error("Enter a patient username.")
            elif not new_patient_password:
                st.error("Enter a patient password.")
            elif len(new_patient_password) < 4:
                st.error("Patient password must contain at least 4 characters.")
            else:
                created, message, patient_data = register_patient(
                    caregiver_id=st.session_state.user["id"],
                    full_name=new_patient_name.strip(),
                    username=new_patient_username.strip(),
                    password=new_patient_password
                )
                if created:
                    patient_id = patient_data["id"]
                    st.success(
                        f"{message} Patient ID: PAT-{patient_id:05d}"
                    )
                    st.rerun()
                else:
                    st.error(message)

    if not patients:
        st.info("Create a Patient ID first.")
        st.stop()

    patient_options = {f"PAT-{p['id']:05d} — {p['full_name']}": p for p in patients}
    with select_col:
        selected_label = st.selectbox("Select Patient", list(patient_options.keys()))
        selected_patient = patient_options[selected_label]
        selected_patient_id = selected_patient["id"]
        selected_patient_name = selected_patient["full_name"]
        st.success(f"Selected Patient ID: PAT-{selected_patient_id:05d}")

    with st.expander("🗑️ Delete this Patient ID", expanded=False):
        st.warning("This permanently deletes the patient account, profile and medicine schedules.")
        confirm_delete = st.checkbox("I understand this cannot be undone.", key=f"confirm_delete_{selected_patient_id}")
        if st.button("Delete Patient ID", key=f"delete_patient_{selected_patient_id}"):
            if not confirm_delete:
                st.error("Please confirm deletion first.")
            else:
                deleted, message = delete_patient(
                    caregiver_id=st.session_state.user["id"],
                    patient_id=selected_patient_id
                )
                if deleted:
                    delete_patient_data(selected_patient_id)
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    existing_profile = get_patient_profile(selected_patient_id)
    profile = dict(existing_profile) if existing_profile else {}
    gender_options = ["", "Male", "Female", "Other", "Prefer not to say"]
    blood_options = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

    with st.form("merged_patient_medicine_form"):
        st.header("1. Patient Details")
        c1, c2 = st.columns(2)
        with c1:
            full_name = st.text_input("Full Name", value=profile.get("full_name", selected_patient_name))
            age = st.number_input("Age", min_value=0, max_value=120, value=int(profile.get("age") or 0), step=1)
            gender = st.selectbox("Gender", gender_options, index=gender_options.index(profile.get("gender", "")) if profile.get("gender", "") in gender_options else 0)
            blood_group = st.selectbox("Blood Group", blood_options, index=blood_options.index(profile.get("blood_group", "")) if profile.get("blood_group", "") in blood_options else 0)
            emergency_contact = st.text_input("Emergency Contact", value=profile.get("emergency_contact", ""))
        with c2:
            allergies = st.text_area("Known Allergies", value=profile.get("allergies", ""))
            medical_conditions = st.text_area("Medical Conditions", value=profile.get("medical_conditions", ""))
            doctor_name = st.text_input("Doctor Name", value=profile.get("doctor_name", ""))
            doctor_contact = st.text_input("Doctor Contact", value=profile.get("doctor_contact", ""))
            additional_notes = st.text_area("Additional Notes", value=profile.get("additional_notes", ""))

        st.header("2. Medicine Details")
        st.caption("Each medicine can be taken multiple times per day. Set separate AM/PM times for every dose.")
        medicine_count = st.number_input("Number of medicines", min_value=1, max_value=10, value=1, step=1)
        medicines = []

        for medicine_number in range(1, int(medicine_count) + 1):
            st.subheader(f"💊 Medicine {medicine_number}")
            m1, m2 = st.columns(2)
            with m1:
                medicine_name = st.text_input("Medicine Name", key=f"medicine_name_{medicine_number}", placeholder="Example: Paracetamol")
                dosage = st.text_input("Dosage per dose", key=f"dosage_{medicine_number}", placeholder="Example: 500 mg / 1 tablet")
                food_instruction = st.selectbox(
                    "Food Instruction",
                    ["After food", "Before food", "With food", "Empty stomach", "With water", "Anytime"],
                    key=f"food_instruction_{medicine_number}"
                )
                start_date = st.date_input("Start Date", value=date.today(), key=f"start_date_{medicine_number}")
                end_date = st.date_input("End Date", value=date.today(), key=f"end_date_{medicine_number}")

            with m2:
                dose_count = st.number_input(
                    f"How many times per day? — Medicine {medicine_number}",
                    min_value=1, max_value=8, value=1, step=1,
                    key=f"dose_count_{medicine_number}"
                )
                doses = []
                for dose_number in range(1, int(dose_count) + 1):
                    st.markdown(f"**Dose {dose_number} time**")
                    tc1, tc2, tc3 = st.columns(3)
                    with tc1:
                        selected_hour = st.selectbox("Hour", list(range(1, 13)), index=7, key=f"hour_{medicine_number}_{dose_number}")
                    with tc2:
                        selected_minute = st.selectbox("Minute", list(range(0, 60)), format_func=lambda x: f"{x:02d}", key=f"minute_{medicine_number}_{dose_number}")
                    with tc3:
                        period = st.selectbox("AM / PM", ["AM", "PM"], key=f"period_{medicine_number}_{dose_number}")
                    converted_hour = 0 if selected_hour == 12 and period == "AM" else (12 if selected_hour == 12 and period == "PM" else (selected_hour + 12 if period == "PM" else selected_hour))
                    doses.append(time(converted_hour, selected_minute))

            medicines.append({
                "medicine_name": medicine_name,
                "dosage": dosage,
                "start_date": start_date,
                "end_date": end_date,
                "doses": doses,
                "food_instruction": food_instruction
            })

        submitted = st.form_submit_button("💾 Save Patient + All Medicines", type="primary")

    if submitted:
        errors = []
        if not full_name.strip():
            errors.append("Full name is required.")
        for number, medicine in enumerate(medicines, start=1):
            if not medicine["medicine_name"].strip() or not medicine["dosage"].strip():
                errors.append(f"Medicine {number}: name and dosage are required.")
            if medicine["end_date"] < medicine["start_date"]:
                errors.append(f"Medicine {number}: end date cannot be before start date.")
        if errors:
            for error in errors:
                st.error(error)
        else:
            save_patient_profile(selected_patient_id, full_name.strip(), int(age), gender, blood_group, emergency_contact, allergies, medical_conditions, doctor_name, doctor_contact, additional_notes)
            schedule = []
            for medicine in medicines:
                current_date = medicine["start_date"]
                while current_date <= medicine["end_date"]:
                    for dose_time in medicine["doses"]:
                        schedule.append({
                            "medicine_name": medicine["medicine_name"].strip(),
                            "dosage": medicine["dosage"].strip(),
                            "date": current_date,
                            "time": dose_time,
                            "food_instruction": medicine["food_instruction"],
                            "status": "Pending",
                            "patient_user_id": selected_patient_id
                        })
                    current_date = current_date.fromordinal(current_date.toordinal() + 1)
            if save_schedule(schedule):
                total_doses = sum(len(m["doses"]) for m in medicines)
                st.success(f"Saved patient details and {len(medicines)} medicine(s) with {total_doses} daily dose time(s) for PAT-{selected_patient_id:05d}.")
            else:
                st.warning("Patient details saved, but this medicine schedule already exists.")


# ==================================================
# PATIENT PROFILE
# ==================================================

if page == "__REMOVED_PATIENT_PROFILE__":
    st.title("👤 Patient Details")
    st.caption("View and update the personal and medical details of the logged-in patient.")

    user_id = st.session_state.user["id"]
    existing_profile = get_patient_profile(user_id)
    profile = dict(existing_profile) if existing_profile else {}

    with st.form("patient_profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name", value=profile.get("full_name", st.session_state.user.get("full_name", "")))
            age = st.number_input("Age", min_value=0, max_value=120, value=int(profile.get("age") or 0), step=1)
            gender_options = ["", "Male", "Female", "Other", "Prefer not to say"]
            current_gender = profile.get("gender", "")
            gender = st.selectbox("Gender", gender_options, index=gender_options.index(current_gender) if current_gender in gender_options else 0)
            blood_options = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
            current_blood = profile.get("blood_group", "")
            blood_group = st.selectbox("Blood Group", blood_options, index=blood_options.index(current_blood) if current_blood in blood_options else 0)
            emergency_contact = st.text_input("Emergency Contact", value=profile.get("emergency_contact", ""))
        with col2:
            allergies = st.text_area("Known Allergies", value=profile.get("allergies", ""))
            medical_conditions = st.text_area("Medical Conditions", value=profile.get("medical_conditions", ""))
            doctor_name = st.text_input("Doctor Name", value=profile.get("doctor_name", ""))
            doctor_contact = st.text_input("Doctor Contact", value=profile.get("doctor_contact", ""))
            additional_notes = st.text_area("Additional Notes", value=profile.get("additional_notes", ""))

        submitted = st.form_submit_button("💾 Save Patient Details", type="primary")

    if submitted:
        if not full_name.strip():
            st.error("Full name is required.")
        else:
            save_patient_profile(
                user_id=user_id, full_name=full_name.strip(), age=int(age),
                gender=gender, blood_group=blood_group,
                emergency_contact=emergency_contact, allergies=allergies,
                medical_conditions=medical_conditions, doctor_name=doctor_name,
                doctor_contact=doctor_contact, additional_notes=additional_notes
            )
            st.success("Patient details saved successfully.")
            st.rerun()


# ==================================================
# PRESCRIPTION SETUP
# ==================================================

if page == "__REMOVED_PRESCRIPTION_SETUP__":

    if user_role != "Caregiver":
        st.error("Only caregivers can add or edit prescriptions.")
        st.stop()

    st.title("💊 Prescription Setup")

    st.write(
        "Enter medicine details and manually select "
        "the exact time for every dose."
    )

    st.info(
        "Example: Select Dose 1 as 8:00 AM and Dose 2 "
        "as 4:00 PM. Both timings will repeat every day."
    )

    # ==================================================
    # 1. MEDICINE DETAILS
    # ==================================================

    st.header("1. Medicine Details")

    medicine_name = st.text_input(
        "Medicine Name",
        placeholder="Example: Paracetamol"
    )

    dosage = st.text_input(
        "Dosage",
        placeholder="Example: 500 mg"
    )

    # ==================================================
    # 2. MEDICATION FREQUENCY
    # ==================================================

    st.header("2. Medication Frequency")

    frequency_type = st.selectbox(
        "How often should the medicine be taken?",
        [
            "Once daily",
            "Twice daily",
            "Three times daily",
            "Four times daily",
            "Every N hours"
        ]
    )

    interval_hours = None

    if frequency_type == "Once daily":

        number_of_doses = 1

    elif frequency_type == "Twice daily":

        number_of_doses = 2

    elif frequency_type == "Three times daily":

        number_of_doses = 3

    elif frequency_type == "Four times daily":

        number_of_doses = 4

    else:

        number_of_doses = 1

        interval_hours = st.number_input(
            "Interval between doses in hours",
            min_value=1,
            max_value=24,
            value=6,
            step=1
        )

    # ==================================================
    # 3. MANUAL DOSE TIMES
    # ==================================================

    st.header("3. Enter Exact Dose Times")

    manual_times = []

    if frequency_type == "Every N hours":

        st.write(
            "Select the first dose time. "
            "The remaining doses will follow the interval."
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            first_hour = st.selectbox(
                "Hour",
                list(range(1, 13)),
                index=7,
                key="first_dose_hour"
            )

        with col2:

            first_minute = st.selectbox(
                "Minute",
                list(range(0, 60)),
                index=0,
                format_func=lambda value: f"{value:02d}",
                key="first_dose_minute"
            )

        with col3:

            first_period = st.selectbox(
                "AM / PM",
                ["AM", "PM"],
                index=0,
                key="first_dose_period"
            )

        first_dose_time = convert_to_24_hour(
            first_hour,
            first_minute,
            first_period
        )

        manual_times.append(
            first_dose_time
        )

    else:

        for dose_number in range(number_of_doses):

            st.subheader(
                f"💊 Dose {dose_number + 1}"
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                selected_hour = st.selectbox(
                    "Hour",
                    list(range(1, 13)),
                    index=7,
                    key=f"dose_hour_{dose_number}"
                )

            with col2:

                selected_minute = st.selectbox(
                    "Minute",
                    list(range(0, 60)),
                    index=0,
                    format_func=lambda value: f"{value:02d}",
                    key=f"dose_minute_{dose_number}"
                )

            with col3:

                selected_period = st.selectbox(
                    "AM / PM",
                    ["AM", "PM"],
                    index=0,
                    key=f"dose_period_{dose_number}"
                )

            selected_time = convert_to_24_hour(
                selected_hour,
                selected_minute,
                selected_period
            )

            manual_times.append(
                selected_time
            )

    # ==================================================
    # 4. START DATE AND DURATION
    # ==================================================

    st.header("4. Start Date and Duration")

    start_date = st.date_input(
        "Start Date",
        value=date.today()
    )

    duration_days = st.number_input(
        "Duration in days",
        min_value=1,
        max_value=365,
        value=1,
        step=1
    )

    # ==================================================
    # 5. FOOD INSTRUCTIONS
    # ==================================================

    st.header("5. Food and Medication Instructions")

    food_instruction = st.selectbox(
        "When should the medicine be taken?",
        [
            "Before food",
            "After food",
            "With food",
            "Empty stomach",
            "With water",
            "No specific instruction",
            "Custom instruction"
        ]
    )

    custom_instruction = ""

    if food_instruction == "Custom instruction":

        custom_instruction = st.text_input(
            "Enter custom instruction",
            placeholder="Example: Take after breakfast"
        )

    # ==================================================
    # 6. GENERATE SCHEDULE
    # ==================================================

    st.header("6. Generate Schedule")

    if st.button(
        "Generate and Save Schedule",
        type="primary"
    ):

        # ==================================================
        # VALIDATION
        # ==================================================

        if not medicine_name.strip():

            st.error(
                "Please enter the medicine name."
            )

        elif not dosage.strip():

            st.error(
                "Please enter the dosage."
            )

        elif (
            frequency_type != "Every N hours"
            and len(set(manual_times)) != len(manual_times)
        ):

            st.error(
                "Please enter different times for each dose."
            )

        elif (
            food_instruction == "Custom instruction"
            and not custom_instruction.strip()
        ):

            st.error(
                "Please enter the custom instruction."
            )

        else:

            # ==================================================
            # FINAL FOOD INSTRUCTION
            # ==================================================

            if food_instruction == "Custom instruction":

                final_instruction = (
                    custom_instruction.strip()
                )

            else:

                final_instruction = food_instruction

            # ==================================================
            # GENERATE SCHEDULE
            # ==================================================

            schedule = generate_schedule(
                medicine_name=medicine_name.strip(),
                dosage=dosage.strip(),
                start_date=start_date,
                manual_times=manual_times,
                interval_hours=interval_hours,
                duration_days=int(duration_days),
                food_instruction=final_instruction
            )

            # ==================================================
            # SAVE SCHEDULE
            # ==================================================

            saved_successfully = save_schedule(
                schedule
            )

            if saved_successfully:

                st.success(
                    f"Schedule saved successfully! "
                    f"{len(schedule)} doses created."
                )

            else:

                st.warning(
                    "This schedule has already been saved."
                )

            # ==================================================
            # DISPLAY GENERATED SCHEDULE
            # ==================================================

            st.subheader(
                "Generated Medication Schedule"
            )

            for index, dose in enumerate(
                schedule,
                start=1
            ):

                dose_datetime = datetime.combine(
                    dose["date"],
                    dose["time"]
                )

                with st.container(border=True):

                    st.write(
                        f"### 💊 Dose {index}"
                    )

                    st.write(
                        f"📅 **Date:** "
                        f"{dose_datetime.strftime('%d %B %Y')}"
                    )

                    st.write(
                        f"⏰ **Time:** "
                        f"{dose_datetime.strftime('%I:%M %p')}"
                    )

                    st.write(
                        f"💊 **Medicine:** "
                        f"{dose['medicine_name']}"
                    )

                    st.write(
                        f"💉 **Dosage:** "
                        f"{dose['dosage']}"
                    )

                    st.write(
                        f"🍽️ **Instruction:** "
                        f"{dose['food_instruction']}"
                    )

                    st.write(
                        f"📌 **Status:** "
                        f"{dose['status']}"
                    )


# ==================================================
# DASHBOARD
# ==================================================

elif page == "Dashboard":

    st.title("📊 Dashboard")

    summary = get_medication_summary()

    total_doses = summary["total_doses"] or 0
    taken_doses = summary["taken_doses"] or 0
    skipped_doses = summary["skipped_doses"] or 0
    missed_doses = summary["missed_doses"] or 0
    snoozed_doses = summary["snoozed_doses"] or 0

    if total_doses > 0:

        adherence_percentage = (
            taken_doses / total_doses
        ) * 100

    else:

        adherence_percentage = 0

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Total Doses",
            total_doses
        )

    with col2:

        st.metric(
            "Taken",
            taken_doses
        )

    with col3:

        st.metric(
            "Adherence",
            f"{adherence_percentage:.1f}%"
        )

    col4, col5, col6 = st.columns(3)

    with col4:

        st.metric(
            "Skipped",
            skipped_doses
        )

    with col5:

        st.metric(
            "Missed",
            missed_doses
        )

    with col6:

        st.metric(
            "Snoozed",
            snoozed_doses
        )

    st.divider()

    saved_prescriptions = get_saved_prescriptions()

    st.subheader("Saved Prescriptions")

    if not saved_prescriptions:

        st.info(
            "No prescriptions have been saved yet."
        )

    else:

        for prescription in saved_prescriptions:

            with st.container(border=True):

                st.write(
                    f"💊 **Medicine:** "
                    f"{prescription['medicine_name']}"
                )

                st.write(
                    f"💉 **Dosage:** "
                    f"{prescription['dosage']}"
                )

                st.write(
                    f"📅 **Start Date:** "
                    f"{prescription['start_date']}"
                )

                st.write(
                    f"📅 **End Date:** "
                    f"{prescription['end_date']}"
                )

                st.write(
                    f"🔢 **Total Doses:** "
                    f"{prescription['total_doses']}"
                )


# ==================================================
# SAVED PRESCRIPTIONS
# ==================================================

elif page == "Saved Prescriptions":

    st.title("📋 Saved Prescriptions")

    prescriptions = get_saved_prescriptions()

    if not prescriptions:

        st.info(
            "No saved prescriptions found."
        )

    else:

        for prescription in prescriptions:

            with st.container(border=True):

                st.subheader(
                    f"💊 {prescription['medicine_name']}"
                )

                st.write(
                    f"💉 **Dosage:** "
                    f"{prescription['dosage']}"
                )

                st.write(
                    f"📅 **Start Date:** "
                    f"{prescription['start_date']}"
                )

                st.write(
                    f"📅 **End Date:** "
                    f"{prescription['end_date']}"
                )

                st.write(
                    f"🔢 **Total Doses:** "
                    f"{prescription['total_doses']}"
                )

                delete_button = st.button(
                    "🗑️ Delete This Prescription",
                    key=f"delete_{prescription['schedule_group_id']}"
                )

                if delete_button:

                    deleted_count = delete_prescription(
                        prescription["schedule_group_id"]
                    )

                    if deleted_count > 0:

                        st.success(
                            "Prescription deleted successfully."
                        )

                        st.rerun()

                    else:

                        st.warning(
                            "Prescription could not be deleted."
                        )


# ==================================================
# TODAY'S MEDICINES
# ==================================================

elif page == "Today's Medicines":

    st.title("📅 Today's Medicines")

    todays_medicines = get_todays_medicines()

    if not todays_medicines:

        st.info(
            "No medicines are scheduled for today."
        )

    else:

        st.success(
            f"{len(todays_medicines)} dose(s) scheduled today."
        )

        for medicine in todays_medicines:

            medicine_time = datetime.strptime(
                medicine["time"],
                "%H:%M:%S"
            )

            with st.container(border=True):

                st.subheader(
                    f"💊 {medicine['medicine_name']}"
                )

                st.write(
                    f"💉 **Dosage:** "
                    f"{medicine['dosage']}"
                )

                st.write(
                    f"⏰ **Time:** "
                    f"{medicine_time.strftime('%I:%M %p')}"
                )

                st.write(
                    f"🍽️ **Instruction:** "
                    f"{medicine['food_instruction']}"
                )

                st.write(
                    f"📌 **Current Status:** "
                    f"{medicine['status']}"
                )

                if user_role == "Caregiver":
                    st.caption("Caregiver controls: update the medicine status.")
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if st.button("✅ Taken", key=f"taken_{medicine['id']}"):
                            update_medication_status(medicine["id"], "Taken")
                            st.rerun()

                    with col2:
                        if st.button("⏰ Snooze", key=f"snooze_{medicine['id']}"):
                            update_medication_status(medicine["id"], "Snoozed")
                            st.rerun()

                    with col3:
                        if st.button("❌ Skipped", key=f"skipped_{medicine['id']}"):
                            update_medication_status(medicine["id"], "Skipped")
                            st.rerun()
                else:
                    st.info("Your caregiver manages prescriptions and updates your medicine status.")


# ==================================================
# MEDICINE ALARM - PATIENT SIDE
# ==================================================

elif page == "Medicine Alarm":

    st.title("🔔 Medicine Alarm")
    st.write("This page uses the prescription schedule set by your caregiver. Keep this page open to receive the alarm.")

    # Refresh the patient alarm page every second so caregiver-set times are checked automatically.
    if st_autorefresh is not None:
        st_autorefresh(interval=1000, key="patient_alarm_refresh")
    else:
        st.warning("Install streamlit-autorefresh for automatic second-by-second alarm checking: pip install streamlit-autorefresh")

    todays_medicines = get_todays_medicines()
    now = datetime.now()

    due_medicines = []
    upcoming_medicines = []

    for medicine in todays_medicines:
        try:
            medicine_time = datetime.strptime(medicine["time"], "%H:%M:%S").time()
            scheduled_datetime = datetime.combine(date.today(), medicine_time)
            if medicine["status"] not in ["Taken", "Skipped"]:
                if scheduled_datetime <= now:
                    due_medicines.append(medicine)
                else:
                    upcoming_medicines.append(medicine)
        except (KeyError, ValueError, TypeError):
            continue

 if due_medicines:
    st.error("🔔 You have medicine reminders requiring attention.")
    st.warning("🔊 Click Start Alarm below to hear the sound.")
        render_alarm_sound()
        for medicine in due_medicines:
            with st.container(border=True):
                st.subheader(f"💊 {medicine['medicine_name']}")
                st.write(f"**Dosage:** {medicine['dosage']}")
                st.write(f"**Scheduled time:** {datetime.strptime(medicine['time'], '%H:%M:%S').strftime('%I:%M %p')}")
                st.write(f"**Instruction:** {medicine['food_instruction']}")
                st.warning("Please follow the prescription provided by your caregiver or doctor.")

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("✅ Taken", key=f"alarm_taken_{medicine['id']}"):
                        update_medication_status(medicine["id"], "Taken")
                        st.rerun()
                with c2:
                    if st.button("⏰ Snooze", key=f"alarm_snooze_{medicine['id']}"):
                        update_medication_status(medicine["id"], "Snoozed")
                        st.rerun()
                with c3:
                    if st.button("❌ Skipped", key=f"alarm_skipped_{medicine['id']}"):
                        update_medication_status(medicine["id"], "Skipped")
                        st.rerun()
    else:
        st.success("🎉 No pending medicine alarm right now.")

    st.subheader("Upcoming medicines")
    if upcoming_medicines:
        for medicine in sorted(upcoming_medicines, key=lambda x: x["time"]):
            scheduled = datetime.strptime(medicine["time"], "%H:%M:%S")
            st.info(f"💊 {medicine['medicine_name']} — {scheduled.strftime('%I:%M %p')} — {medicine['dosage']}")
    else:
        st.write("No upcoming medicines for today.")


# ==================================================
# MEDICINE CHATBOT - PATIENT SIDE
# ==================================================

elif page == "Medicine Chatbot":

    st.title("🤖 Medicine Chatbot")
    st.caption("Ask questions about your caregiver-created medicine schedule.")

    todays_medicines = get_todays_medicines()
    history = get_medication_history()

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "Hello! I can help you check your medicine schedule, next dose, pending medicines and medication history."}
        ]

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_question = st.chat_input("Ask: What medicine do I take next?")

    if user_question:
        st.session_state.chat_messages.append({"role": "user", "content": user_question})
        question = user_question.lower().strip()

        if not todays_medicines:
            answer = "There are no medicines scheduled for today. Please contact your caregiver if this seems incorrect."
        elif any(word in question for word in ["today", "schedule", "medicines", "medicine"]):
            lines = []
            for medicine in todays_medicines:
                dose_time = datetime.strptime(medicine["time"], "%H:%M:%S").strftime("%I:%M %p")
                lines.append(f"• {medicine['medicine_name']} — {medicine['dosage']} at {dose_time} — {medicine['food_instruction']} — Status: {medicine['status']}")
            answer = "Here is your medicine schedule for today:\n\n" + "\n".join(lines)
        elif "next" in question or "upcoming" in question:
            pending = [m for m in todays_medicines if m["status"] not in ["Taken", "Skipped"]]
            if pending:
                next_medicine = sorted(pending, key=lambda x: x["time"])[0]
                dose_time = datetime.strptime(next_medicine["time"], "%H:%M:%S").strftime("%I:%M %p")
                answer = f"Your next pending medicine is {next_medicine['medicine_name']} ({next_medicine['dosage']}) at {dose_time}. Instruction: {next_medicine['food_instruction']}."
            else:
                answer = "You have no pending medicines for today."
        elif "pending" in question or "missed" in question:
            pending = [m for m in todays_medicines if m["status"] not in ["Taken", "Skipped"]]
            answer = f"You have {len(pending)} pending medicine dose(s) today."
        elif "history" in question or "taken" in question or "status" in question:
            if history:
                recent = history[:5]
                answer = "Recent medication history:\n\n" + "\n".join(
                    f"• {m['medicine_name']} — {m['date']} {m['time']} — {m['status']}" for m in recent
                )
            else:
                answer = "No medication history is available yet."
        elif "dosage" in question or "dose" in question:
            answer = "Your dosage is shown beside each medicine in Today’s Medicines. Dosage changes must be made by your caregiver or doctor."
        else:
            answer = "I can show today’s medicines, your next dose, pending medicines, dosage details and medication history. I cannot change prescriptions or provide medical advice."

        st.session_state.chat_messages.append({"role": "assistant", "content": answer})
        st.rerun()


# ==================================================
# MEDICATION HISTORY
# ==================================================

elif page == "Medication History":

    st.title("📜 Medication History")

    history = get_medication_history()

    if not history:

        st.info(
            "No medication history available yet."
        )

    else:

        for medicine in history:

            medicine_datetime = datetime.strptime(
                f"{medicine['date']} {medicine['time']}",
                "%Y-%m-%d %H:%M:%S"
            )

            with st.container(border=True):

                st.write(
                    f"💊 **Medicine:** "
                    f"{medicine['medicine_name']}"
                )

                st.write(
                    f"💉 **Dosage:** "
                    f"{medicine['dosage']}"
                )

                st.write(
                    f"📅 **Date:** "
                    f"{medicine_datetime.strftime('%d %B %Y')}"
                )

                st.write(
                    f"⏰ **Time:** "
                    f"{medicine_datetime.strftime('%I:%M %p')}"
                )

                st.write(
                    f"🍽️ **Instruction:** "
                    f"{medicine['food_instruction']}"
                )

                st.write(
                    f"📌 **Status:** "
                    f"{medicine['status']}"
                )


# ==================================================
# CAREGIVER DASHBOARD
# ==================================================

elif page == "Caregiver Dashboard":

    if user_role != "Caregiver":
        st.error("This dashboard is available only to caregivers.")
        st.stop()

    st.title("👨‍👩‍👧 Caregiver Dashboard")

    summary = get_medication_summary()

    total_doses = summary["total_doses"] or 0
    taken_doses = summary["taken_doses"] or 0
    skipped_doses = summary["skipped_doses"] or 0
    missed_doses = summary["missed_doses"] or 0
    snoozed_doses = summary["snoozed_doses"] or 0

    if total_doses > 0:

        adherence_percentage = (
            taken_doses / total_doses
        ) * 100

    else:

        adherence_percentage = 0

    st.subheader("Patient Medication Overview")

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Total Doses",
            total_doses
        )

        st.metric(
            "Taken Doses",
            taken_doses
        )

        st.metric(
            "Skipped Doses",
            skipped_doses
        )

    with col2:

        st.metric(
            "Missed Doses",
            missed_doses
        )

        st.metric(
            "Snoozed Doses",
            snoozed_doses
        )

        st.metric(
            "Patient Adherence",
            f"{adherence_percentage:.1f}%"
        )

    st.divider()

    st.write("Planned caregiver features:")

    st.write("- Missed-dose alerts")
    st.write("- Patient adherence percentage")
    st.write("- Medicine-wise history")
    st.write("- Caregiver notification integration")
