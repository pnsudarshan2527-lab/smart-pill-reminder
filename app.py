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
    get_medication_summary
)

from auth import (
    initialize_auth_database,
    register_user,
    register_patient,
    login_user,
    get_caregiver_patients,
    check_patient_access,
    delete_patient
)

# ==================================================
# ALARM SOUND HELPER
# ==================================================

def render_alarm_sound():
    """Render a repeating alarm sound in the browser."""
    sample_rate = 44100
    duration = 0.6
    frames = []

    for i in range(int(sample_rate * duration)):
        t = i / sample_rate
        # Two-tone beep for a clear reminder sound
        frequency = 880 if int(t * 4) % 2 == 0 else 660
        value = int(15000 * math.sin(2 * math.pi * frequency * t))
        frames.append(value)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"".join(int(x).to_bytes(2, byteorder="little", signed=True) for x in frames))

    audio_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    components.html(
        f"""
        <audio autoplay loop controls style="width:100%;">
            <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
        </audio>
        <script>
            const audio = document.querySelector('audio');
            audio.volume = 1.0;
            audio.play().catch(() => {{
                document.body.insertAdjacentHTML('beforeend',
                    '<p style=\"color:#b45309;font-size:13px;\">Click Play if your browser blocks automatic sound.</p>');
            }});
        </script>
        """,
        height=80,
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

if user_role.lower() == "caregiver":
    navigation_options = [
        "Dashboard",
        "Prescription Setup",
        "Saved Prescriptions",
        "Today's Medicines",
        "Medication History",
        "Caregiver Dashboard"
    ]
else:
    navigation_options = [
        "Dashboard",
        "Today's Medicines",
        "Medicine Alarm",
        "Medicine Chatbot",
        "Medication History"
    ]

page = st.sidebar.radio("Navigation", navigation_options)


# ==================================================
# PRESCRIPTION SETUP
# ==================================================

if page == "Prescription Setup":

    if user_role.lower() != "caregiver":
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

                if user_role.lower() == "caregiver":
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
        st.warning("🔊 Alarm is due. If Chrome blocks autoplay, click Play once in the audio player.")
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

    if user_role.lower() != "caregiver":
        st.error("This dashboard is available only to caregivers.")
        st.stop()

    st.title("👨‍👩‍👧 Caregiver Dashboard")

    caregiver_id = st.session_state.user["id"]
    patients = get_caregiver_patients(caregiver_id)

    st.subheader("Manage Patients")
    with st.expander("➕ Add a new patient", expanded=not bool(patients)):
        with st.form("add_patient_form"):
            patient_name = st.text_input("Patient full name")
            patient_username = st.text_input("Patient username")
            patient_password = st.text_input("Temporary password", type="password")
            relationship = st.selectbox("Relationship", ["Parent", "Spouse", "Child", "Sibling", "Relative", "Other"])
            add_patient = st.form_submit_button("Add Patient")

            if add_patient:
                if not patient_name or not patient_username or not patient_password:
                    st.error("Please fill in all patient fields.")
                else:
                    ok, msg, _ = register_patient(
                        caregiver_id=caregiver_id,
                        full_name=patient_name,
                        username=patient_username,
                        password=patient_password,
                        relationship=relationship
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    if patients:
        patient_options = {
            f"{p['full_name']} ({p['username']})": p for p in patients
        }
        selected_label = st.selectbox("Select patient", list(patient_options.keys()))
        selected_patient = patient_options[selected_label]
        st.session_state.selected_patient = selected_patient
        st.info(f"Currently viewing: **{selected_patient['full_name']}** | Relationship: {selected_patient.get('relationship', 'Patient')}")

        st.warning("Deleting a patient permanently removes their login account. This action cannot be undone.")
        confirm_delete = st.checkbox(
            f"I confirm that I want to delete {selected_patient['full_name']}'s account",
            key=f"confirm_delete_{selected_patient['id']}"
        )
        if st.button("🗑️ Delete Selected Patient", type="secondary", disabled=not confirm_delete):
            deleted, delete_message = delete_patient(caregiver_id, selected_patient['id'])
            if deleted:
                st.session_state.pop("selected_patient", None)
                st.success(delete_message)
                st.rerun()
            else:
                st.error(delete_message)
    else:
        st.warning("No patients linked yet. Add your first patient above.")

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