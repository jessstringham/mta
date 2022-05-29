from collections import namedtuple


Color = namedtuple("Color", ["color", "message"])


class StopConfig:
    COLOR_GETTING_CLOSE = Color((100, 0, 0), "close")
    TIMING_GETTING_CLOSE = 2  # before this, turn red
    COLOR_HAVE_TIME = Color((100, 100, 0), "good time to leave")
    TIMING_HAVE_TIME = 5  # before this, turn green
    COLOR_CAN_WAIT = Color((0, 0, 100), "get ready")
    TIMING_CAN_WAIT = 10  # after this, turn gray
    COLOR_TOO_FAR = Color((20, 20, 20), "too far")
    TIMING_TOO_FAR = 20  # after this, turn off
    COLOR_WAY_TOO_FAR = Color((0, 0, 0), "way too far")
