# SafeGuard AI — Database Documentation

## Overview
The SafeGuard AI application utilizes a relational database to persist system settings, historical safety violations, and operational metrics. By default, it uses SQLite (`safeguard.db`) for lightweight, zero-configuration deployment, but the ORM architecture allows easy migration to PostgreSQL or MySQL if necessary.

## Tech Stack
- **Database:** SQLite (default)
- **ORM:** SQLAlchemy
- **Migration Engine:** Alembic (if configured for schema migrations)

## Configuration & Connection
Database setup is located in `backend/db/database.py`. 
- The `DATABASE_URL` is loaded from the environment variables (e.g., `sqlite:///./safeguard.db`).
- An SQLAlchemy `Engine` and a `SessionLocal` maker are initialized.
- A declarative `Base` is instantiated for model definitions.

The FastAPI dependency injection pattern (`get_db`) is used to provide database sessions to API routes, ensuring sessions are safely closed after requests complete.

## Data Models (`backend/db/models.py`)

### 1. `Violation` Table
Stores records of all detected safety infractions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `timestamp` | DateTime | When the violation occurred (default: UTC now) |
| `violation_type` | String | E.g., "Missing PPE", "Unauthorized Area" |
| `person_count` | Integer | Number of people involved in the frame |
| `confidence` | Float | Model's confidence score for the detection |
| `missing_ppe` | String | Comma-separated list of missing gear (e.g., "Helmet, Safety Vest") |
| `screenshot_path` | String | URL path to the saved annotated image |

### 2. `AlertSettings` Table
Stores the user-configurable rules for detection and notifications. Typically, there is only one row in this table that gets updated.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key (usually `1`) |
| `email_enabled` | Boolean | Global toggle for email alerts |
| `email_recipients` | JSON/String | List of target email addresses |
| `email_cooldown` | Integer | Minimum seconds between consecutive email alerts |
| `whatsapp_enabled` | Boolean | Global toggle for WhatsApp alerts |
| `whatsapp_recipient` | String | Target phone number for WhatsApp alerts |
| `whatsapp_cooldown` | Integer | Minimum seconds between consecutive WhatsApp alerts |
| `confidence_threshold` | Float | Minimum threshold (0.0 - 1.0) for an object to be considered valid |
| `require_helmet` | Boolean | Flag indicating if a helmet must be present on detected persons |
| `require_vest` | Boolean | Flag indicating if a vest must be present on detected persons |

## Database Initialization
Upon starting the FastAPI application (`main.py`), SQLAlchemy's `Base.metadata.create_all(bind=engine)` is called. This automatically creates the tables in the SQLite file if they do not already exist.

When querying or updating settings via the API, the system automatically checks if an `AlertSettings` row exists; if not, it seeds the database with default values.
