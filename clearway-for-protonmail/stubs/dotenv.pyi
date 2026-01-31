from typing import overload

def load_dotenv(
    dotenv_path: str | None = None,
    stream: object | None = None,
    verbose: bool = False,
    override: bool = False,
    interpolate: bool = True,
    encoding: str | None = "utf-8",
) -> bool:
    """Load environment variables from a .env file.

    Args:
        dotenv_path: Path to the .env file. If None, searches for .env in current directory.
        stream: Text stream to read from (alternative to dotenv_path).
        verbose: Whether to print debug messages.
        override: Whether to override existing environment variables.
        interpolate: Whether to interpolate variables.
        encoding: Encoding to use when reading the file.

    Returns:
        True if at least one environment variable was loaded, False otherwise.
    """
    ...

def find_dotenv(
    filename: str = ".env", raise_error_if_not_found: bool = False, usecwd: bool = False
) -> str | None:
    """Search for a .env file in the directory hierarchy.

    Args:
        filename: Name of the file to search for.
        raise_error_if_not_found: Whether to raise an error if file not found.
        usecwd: Whether to use current working directory as starting point.

    Returns:
        Path to the .env file or None if not found.
    """
    ...

def get_key(dotenv_path: str, key_to_get: str) -> str | None:
    """Get a key from a .env file.

    Args:
        dotenv_path: Path to the .env file.
        key_to_get: Key to retrieve.

    Returns:
        Value of the key or None if not found.
    """
    ...

def set_key(
    dotenv_path: str,
    key_to_set: str,
    value_to_set: str,
    quote_mode: str = "always",
    export: bool = False,
    encoding: str | None = "utf-8",
) -> tuple[bool, str, str | None]:
    """Set a key in a .env file.

    Args:
        dotenv_path: Path to the .env file.
        key_to_set: Key to set.
        value_to_set: Value to set.
        quote_mode: Quoting mode ("always", "auto", "never").
        export: Whether to add export keyword.
        encoding: Encoding to use.

    Returns:
        Tuple of (success, key, value).
    """
    ...

def unset_key(
    dotenv_path: str,
    key_to_unset: str,
    quote_mode: str = "always",
    encoding: str | None = "utf-8",
) -> tuple[bool, str]:
    """Remove a key from a .env file.

    Args:
        dotenv_path: Path to the .env file.
        key_to_unset: Key to remove.
        quote_mode: Quoting mode.
        encoding: Encoding to use.

    Returns:
        Tuple of (success, key).
    """
    ...

def dotenv_values(
    dotenv_path: str | None = None,
    stream: object | None = None,
    verbose: bool = False,
    interpolate: bool = True,
    encoding: str | None = "utf-8",
) -> dict[str, str | None]:
    """Parse a .env file and return a dict of key-value pairs.

    Args:
        dotenv_path: Path to the .env file.
        stream: Text stream to read from.
        verbose: Whether to print debug messages.
        interpolate: Whether to interpolate variables.
        encoding: Encoding to use.

    Returns:
        Dictionary of environment variables.
    """
    ...
