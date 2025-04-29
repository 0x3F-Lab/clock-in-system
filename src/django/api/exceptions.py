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


class InactiveUserError(Exception):
    """
    Raised when attempting to interact with an inactive user.
    """

    def __init__(
        self,
        message="Employee is marked as inactive, cannot interact with the account.",
    ):
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


class BadLocationDataError(Exception):
    """
    Raised when the location data (lat/long) is incorrectly given. I.e. not a float.
    """

    def __init__(
        self, message="Location data is incorrectly formed. I.e. not a float."
    ):
        self.message = message
        super().__init__(self.message)


class InvalidLocationError(Exception):
    """
    Raised when a clock in/out request is too far from the store's range.
    """

    def __init__(self, message="Request is made too far from the store."):
        self.message = message
        super().__init__(self.message)


class MissingPinError(Exception):
    """
    Raised when a clock in/out request is missing a hashed pin for authentication.
    """

    def __init__(self, message="Request is missing authentication pin."):
        self.message = message
        super().__init__(self.message)


class MissingPasswordError(Exception):
    """
    Raised when a manager authentication is missing the password.
    """

    def __init__(self, message="Request is missing a password."):
        self.message = message
        super().__init__(self.message)


class InvalidPinError(Exception):
    """
    Raised when a clock in/out request is performed with an invalid pin for the employee.
    """

    def __init__(self, message="Employee pin is invalid."):
        self.message = message
        super().__init__(self.message)


class InvalidPasswordError(Exception):
    """
    Raised when a login attempt is made with an invalid password.
    """

    def __init__(self, message="Employee password is invalid."):
        self.message = message
        super().__init__(self.message)


class StartingShiftTooSoonError(Exception):
    """
    Raised when an attempt is made to start a shift toon soon after their last shift.
    """

    def __init__(self, message="Can not start a shift too soon after the last shift."):
        self.message = message
        super().__init__(self.message)


class ClockingOutTooSoonError(Exception):
    """
    Raised when an attempt is made to clock out too soon after clocking in.
    """

    def __init__(self, message="Can not clock out too soon after clocking in."):
        self.message = message
        super().__init__(self.message)


class NotAssociatedWithStore(Exception):
    """
    Raised when an attempt is made to interact with a store the user is not associated with.
    """

    def __init__(self, message="Can not interact with a non-associated store."):
        self.message = message
        super().__init__(self.message)
