from datetime import datetime, timedelta
from uuid import uuid4


def generate_schedule(
    medicine_name,
    dosage,
    start_date,
    manual_times,
    interval_hours,
    duration_days,
    food_instruction
):
    """
    Generate a medication schedule.

    Daily example:
        8:00 AM and 4:00 PM

    Every N hours example:
        First dose: 8:00 AM
        Interval: 6 hours
    """

    schedule = []

    # One unique ID for the complete prescription.
    # All doses created for this prescription share this ID.
    schedule_group_id = str(uuid4())

    # ==================================================
    # EVERY N HOURS
    # ==================================================

    if interval_hours is not None:

        first_dose_time = manual_times[0]

        current_datetime = datetime.combine(
            start_date,
            first_dose_time
        )

        end_datetime = current_datetime + timedelta(
            days=duration_days
        )

        while current_datetime < end_datetime:

            schedule.append(
                {
                    "schedule_group_id": schedule_group_id,
                    "medicine_name": medicine_name,
                    "dosage": dosage,
                    "date": current_datetime.date(),
                    "time": current_datetime.time(),
                    "food_instruction": food_instruction,
                    "status": "Pending"
                }
            )

            current_datetime += timedelta(
                hours=int(interval_hours)
            )

    # ==================================================
    # DAILY MANUAL TIMES
    # ==================================================

    else:

        # Every manually entered time repeats every day.
        #
        # Example:
        # 8:00 AM and 4:00 PM
        #
        # Both times repeat for every selected day.

        sorted_times = sorted(manual_times)

        for day_number in range(duration_days):

            current_date = (
                start_date + timedelta(days=day_number)
            )

            for selected_time in sorted_times:

                dose_datetime = datetime.combine(
                    current_date,
                    selected_time
                )

                schedule.append(
                    {
                        "schedule_group_id": schedule_group_id,
                        "medicine_name": medicine_name,
                        "dosage": dosage,
                        "date": dose_datetime.date(),
                        "time": dose_datetime.time(),
                        "food_instruction": food_instruction,
                        "status": "Pending"
                    }
                )

    # ==================================================
    # SORT SCHEDULE
    # ==================================================

    schedule.sort(
        key=lambda dose: datetime.combine(
            dose["date"],
            dose["time"]
        )
    )

    return schedule