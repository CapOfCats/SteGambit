"""SteGambit custom exception hierarchy.

All exceptions inherit from StegambitError, so they can be caught with a single except at the UI boundary

Each exception carries a human-readable error.
"""


class StegambitError(Exception):
    """Base application exception. All domain errors inherit from it."""


class CompatibilityError(StegambitError):
    """The format is unsupported, capacity is insufficient, or conversion is forbidden."""


class CapacityExceededError(CompatibilityError):
    """The payload does not fit in the container. A specialization of CompatibilityError.

    Reserved for the future: if we want to distinguish "format not supported"
    from "format is OK, but there is not enough room", the frontend can check via isinstance.
    """


class InvalidFrameError(StegambitError):
    """MAGIC bytes were not found in the container, or the header is corrupt.

    Most likely the password is wrong, or the file contains no data at all.
    """

class InvalidPasswordError(InvalidFrameError):
    """Wrong password or corrupt data.

    AES-GCM cannot distinguish a wrong key from corrupt data — both produce the same result: a tag mismatch.
    """

class CorruptedCarrierError(StegambitError):
    """The container cannot be read (battered beyond use)."""
