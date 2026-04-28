"""
Household economics backend package.

The ``app`` package exposes the FastAPI application via ``main.py`` and
contains all database models and Pydantic schemas. Importing this
package has no side effects; the database is initialised explicitly
when the application starts up.
"""

__all__ = ["models", "schemas", "database", "main"]