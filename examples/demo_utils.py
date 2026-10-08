"""Shared output validation for the two demo entry points."""
from pathlib import Path


def checked_output(value, database):
    if value is None:
        return None
    output = Path(value).resolve()
    database = Path(database).resolve()
    if output == database or output.is_relative_to(database.parent / 'sources'):
        raise ValueError('JSON output cannot overwrite the database or saved source files')
    if output.suffix.lower() != '.json':
        raise ValueError('Demo output must use the .json extension')
    return output
