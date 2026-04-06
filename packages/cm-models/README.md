# CM Service Models
This package includes object models and templates used by CM Service.
These models include database and pydantic models.
The database models use the `sqlmodel` package and are hybrid pydantic/sqlalchemy models.
These are used throughout the CM Service to represent database-backed objects.
Pydantic models are used mostly in APIs and user interfaces to represent CM objects that are not necessarily database-oriented.

## Installation
This package is not currently built or published separately to CM Service.
The best way to install this package is to use the `uv` tool with the `--package` argument.
