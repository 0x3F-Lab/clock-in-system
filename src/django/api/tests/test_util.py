import pytest
import api.utils as util
from datetime import datetime


def test_get_distance_from_lat_lon_in_m():
    """
    Test the distance calculation between two points.
    """
    lat1, lon1 = 1.0, 1.0
    lat2, lon2 = 1.001, 1.001  # Slightly different point
    distance = util.get_distance_from_lat_lon_in_m(lat1, lon1, lat2, lon2)
    assert distance > 0  # Should return a positive distance
    assert distance < 200  # Within expected small range


# Test for rounding datetime function
@pytest.mark.parametrize(
    "dt, rounding_mins, expected_rounded_dt",
    [
        (
            datetime(2024, 12, 19, 14, 37),
            15,
            datetime(2024, 12, 19, 14, 30),
        ),  # Round to 14:30
        (
            datetime(2024, 12, 19, 14, 42),
            15,
            datetime(2024, 12, 19, 14, 45),
        ),  # Round to 14:45
        (
            datetime(2024, 12, 19, 14, 58),
            15,
            datetime(2024, 12, 19, 15, 0),
        ),  # Round to 15:00
        (
            datetime(2024, 12, 19, 23, 58),
            15,
            datetime(2024, 12, 20, 0, 0),
        ),  # Round to next day
    ],
)
def test_round_datetime_minute(dt, rounding_mins, expected_rounded_dt):
    rounded_dt = util.round_datetime_minute(dt, rounding_mins)
    assert rounded_dt == expected_rounded_dt


# Test for calculating shift length function
def test_calculate_shift_length_mins():
    start = datetime(2024, 12, 19, 9, 0)
    end = datetime(2024, 12, 19, 17, 0)

    shift_length = util.calculate_shift_length_mins(start, end)
    assert shift_length == 480  # 8 hours = 480 minutes
