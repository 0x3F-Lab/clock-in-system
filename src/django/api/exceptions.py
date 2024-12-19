class AlreadyClockedInError(Exception):
    """
    Raised when an attempt is made to clock in a user who is already clocked in.
    """

    def __init__(self, message="Employee is already clocked in."):
        self.message = message
        super().__init__(self.message)


class AlreadyClockedOutError(Exception):
    """
    Raised when an attempt is made to clock out a user who is already clocked out.
    """

    def __init__(self, message="Employee is already clocked out."):
        self.message = message
        super().__init__(self.message)


class NoActiveClockingRecordError(Exception):
    """
    Raised when an attempt is made to clock out a user who has no active shift where they are clocked in. (Missing the clock-in activity).
    """

    def __init__(self, message="Employee is missing an active clocking record."):
        self.message = message
        super().__init__(self.message)


class MissingLocationDataError(Exception):
    """
    Raised when a clock in/out request is missing either of the location tags (lat/long).
    """

    def __init__(self, message="Request is missing location data."):
        self.message = message
        super().__init__(self.message)
