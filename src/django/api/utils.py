from datetime import datetime, timedelta
from django.utils.timezone import now


# Function to check if a given date is a public holiday
def is_public_holiday(time):
    date = time.date()

    ### USE API CALLS TO CHECK FOR PUBLIC HOLIDAYS!!!

    public_holidays = [
        datetime(2024, 12, 25).date(),  # Example: Christmas Day
        datetime(2024, 1, 1).date(),  # Example: New Year's Day
    ]

    return date in public_holidays


# Function to round the time to the nearest specified minute
def round_datetime_minute(dt, rounding_mins=15):
    # Calculate the total number of minutes since midnight
    total_minutes = dt.hour * 60 + dt.minute

    # Find the remainder when dividing total minutes by rounding_mins
    remainder = total_minutes % rounding_mins

    # If remainder is greater than or equal to half of rounding_mins, round up
    if remainder >= rounding_mins / 2:
        # Round up
        rounded_minutes = total_minutes + (rounding_mins - remainder)
    else:
        # Round down
        rounded_minutes = total_minutes - remainder

    # Calculate the new rounded time
    rounded_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        minutes=rounded_minutes
    )

    # Return the rounded datetime
    return rounded_dt


# Function to calculate the total time in a shift (in minutes)
def calculate_shift_length_mins(start, end):
    # Calculate difference between events
    time_diff = end - start

    # Calculate the total shift time in minutes
    total_minutes = time_diff.total_seconds() / 60

    return total_minutes
