"""Exception classes for libteamsdb."""


class TeamsDatabaseError(Exception):
    """Base exception for all libteamsdb errors."""

    pass


class DatabaseNotFoundError(TeamsDatabaseError):
    """Raised when no Teams database can be found."""

    pass


class InvalidDatabaseError(TeamsDatabaseError):
    """Raised when the database exists but is corrupted or invalid."""

    pass


class ExtractionError(TeamsDatabaseError):
    """Raised when data extraction fails."""

    pass
