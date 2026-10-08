class DataError(ValueError):
    """Invalid input or an unsupported data/schema condition."""


class SourceIntegrityError(DataError):
    """A saved original is missing, changed or outside the evidence directory."""
