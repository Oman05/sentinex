import secrets

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.database.base import Base

connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_reference_images_schema()
    _migrate_departments_schema()
    _migrate_cameras_schema()
    _migrate_evidence_schema()
    _migrate_users_schema()
    _migrate_processing_events_schema()
    _migrate_face_quality_schema()
    _migrate_match_events_schema()
    _migrate_review_events_schema()
    _seed_default_users()


def _migrate_departments_schema() -> None:
    """Safely adds newly required columns to departments if the table pre-existed."""
    try:
        inspector = inspect(engine)
        if "departments" not in inspector.get_table_names():
            return

        existing_columns = {col["name"] for col in inspector.get_columns("departments")}

        column_defs = {
            "department_code": "VARCHAR(50)",
            "jurisdiction": "VARCHAR(150)",
            "latitude": "FLOAT",
            "longitude": "FLOAT",
            "contact_email": "VARCHAR(255)",
            "contact_phone": "VARCHAR(50)",
            "notification_enabled": "BOOLEAN DEFAULT 1",
            "is_central": "BOOLEAN DEFAULT 0",
        }

        with engine.begin() as conn:
            for col_name, col_type in column_defs.items():
                if col_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE departments ADD COLUMN {col_name} {col_type}"))
    except Exception:
        pass


def _migrate_cameras_schema() -> None:
    """Safely adds newly required columns to cameras if the table pre-existed."""
    try:
        inspector = inspect(engine)
        if "cameras" not in inspector.get_table_names():
            return
        existing_columns = {col["name"] for col in inspector.get_columns("cameras")}
        column_defs = {
            "processing_enabled": "BOOLEAN DEFAULT 1",
            "sampling_interval": "FLOAT DEFAULT 1.0",
        }
        with engine.begin() as conn:
            for col_name, col_type in column_defs.items():
                if col_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE cameras ADD COLUMN {col_name} {col_type}"))
    except Exception:
        pass


def _migrate_evidence_schema() -> None:
    """
    Ensure Module 10 evidence tables exist.
    New tables are created by Base.metadata.create_all() above.
    This function handles any column additions to pre-existing tables.
    """
    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        # evidence_items additional columns (if table pre-dates module 10 additions)
        if "evidence_items" in table_names:
            existing = {col["name"] for col in inspector.get_columns("evidence_items")}
            extra_cols = {
                "clip_start_time": "DATETIME",
                "clip_end_time": "DATETIME",
                "clip_duration_seconds": "FLOAT",
                "clip_generation_method": "VARCHAR(100)",
                "storage_backend": "VARCHAR(30) DEFAULT 'LOCAL'",
                "original_file_name": "VARCHAR(255)",
                "integrity_status": "VARCHAR(30) DEFAULT 'NOT_VERIFIED'",
                "last_integrity_check_at": "DATETIME",
                "version_number": "INTEGER DEFAULT 1",
                "version_notes": "TEXT",
                "tags": "VARCHAR(500)",
                "retention_expires_at": "DATETIME",
            }
            with engine.begin() as conn:
                for col_name, col_type in extra_cols.items():
                    if col_name not in existing:
                        conn.execute(text(f"ALTER TABLE evidence_items ADD COLUMN {col_name} {col_type}"))
    except Exception:
        pass


def _migrate_reference_images_schema() -> None:
    """Safely adds newly required columns to reference_images if the table pre-existed."""
    try:
        inspector = inspect(engine)
        if "reference_images" not in inspector.get_table_names():
            return

        existing_columns = {col["name"] for col in inspector.get_columns("reference_images")}

        column_defs = {
            "file_name": "VARCHAR(255)",
            "original_file_name": "VARCHAR(255)",
            "storage_type": "VARCHAR(50) DEFAULT 'LOCAL'",
            "mime_type": "VARCHAR(50)",
            "image_width": "INTEGER",
            "image_height": "INTEGER",
            "created_at": "DATETIME",
            "image_quality_status": "VARCHAR(50) DEFAULT 'PENDING'",
            "processing_status": "VARCHAR(50) DEFAULT 'PENDING'",
            "feature_reference_id": "VARCHAR(100)",
            "notes": "TEXT",
        }

        with engine.begin() as conn:
            for col_name, col_type in column_defs.items():
                if col_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE reference_images ADD COLUMN {col_name} {col_type}"))

            # Populate new columns from legacy columns if present
            if "stored_filename" in existing_columns and "file_name" in existing_columns:
                conn.execute(text("UPDATE reference_images SET file_name = stored_filename WHERE file_name IS NULL"))
            if "original_filename" in existing_columns and "original_file_name" in existing_columns:
                conn.execute(text("UPDATE reference_images SET original_file_name = original_filename WHERE original_file_name IS NULL"))
            if "file_type" in existing_columns and "mime_type" in existing_columns:
                conn.execute(text("UPDATE reference_images SET mime_type = file_type WHERE mime_type IS NULL"))
            if "width" in existing_columns and "image_width" in existing_columns:
                conn.execute(text("UPDATE reference_images SET image_width = width WHERE image_width IS NULL"))
            if "height" in existing_columns and "image_height" in existing_columns:
                conn.execute(text("UPDATE reference_images SET image_height = height WHERE image_height IS NULL"))
            if "uploaded_at" in existing_columns and "created_at" in existing_columns:
                conn.execute(text("UPDATE reference_images SET created_at = uploaded_at WHERE created_at IS NULL"))
    except Exception:
        # Avoid crashing startup if database dialect handles schema differently
        pass


def _migrate_users_schema() -> None:
    try:
        inspector = inspect(engine)
        if "users" not in inspector.get_table_names():
            return
        existing_columns = {col["name"] for col in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "department_id" not in existing_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN department_id INTEGER"))
            if "last_login_at" not in existing_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at DATETIME"))
    except Exception:
        pass


def _migrate_processing_events_schema() -> None:
    try:
        inspector = inspect(engine)
        if "processing_events" not in inspector.get_table_names():
            return
        existing_columns = {col["name"] for col in inspector.get_columns("processing_events")}
        with engine.begin() as conn:
            if "people_count" not in existing_columns:
                conn.execute(text("ALTER TABLE processing_events ADD COLUMN people_count INTEGER DEFAULT 0"))
    except Exception:
        pass


def _migrate_face_quality_schema() -> None:
    try:
        inspector = inspect(engine)
        if "face_quality_results" not in inspector.get_table_names():
            return
        existing_columns = {col["name"] for col in inspector.get_columns("face_quality_results")}
        with engine.begin() as conn:
            if "passed_quality_gate" not in existing_columns:
                conn.execute(text("ALTER TABLE face_quality_results ADD COLUMN passed_quality_gate BOOLEAN DEFAULT 0"))
            if "processing_time_ms" not in existing_columns:
                conn.execute(text("ALTER TABLE face_quality_results ADD COLUMN processing_time_ms FLOAT"))
    except Exception:
        pass


def _migrate_match_events_schema() -> None:
    try:
        inspector = inspect(engine)
        if "match_events" not in inspector.get_table_names():
            return
        existing_columns = {col["name"] for col in inspector.get_columns("match_events")}
        with engine.begin() as conn:
            if "search_latency_ms" not in existing_columns:
                conn.execute(text("ALTER TABLE match_events ADD COLUMN search_latency_ms FLOAT"))
    except Exception:
        pass


def _migrate_review_events_schema() -> None:
    try:
        inspector = inspect(engine)
        if "review_events" not in inspector.get_table_names():
            return
        existing_columns = {col["name"] for col in inspector.get_columns("review_events")}
        column_defs = {
            "review_completed_at": "DATETIME",
            "face_quality_label": "VARCHAR(50)",
            "detection_quality_score": "FLOAT",
            "observation_count": "INTEGER DEFAULT 1",
            "priority": "VARCHAR(20) DEFAULT 'MEDIUM'",
        }
        with engine.begin() as conn:
            for col_name, col_type in column_defs.items():
                if col_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE review_events ADD COLUMN {col_name} {col_type}"))
    except Exception:
        pass


def _seed_default_users() -> None:
    """Ensure initial admin and police accounts exist if users table is empty."""
    try:
        from app.core.security import hash_password
        with SessionLocal() as db:
            user_count = db.execute(text("SELECT count(*) FROM users")).scalar()
            if not user_count:
                admin_password = secrets.token_urlsafe(24)
                police_password = secrets.token_urlsafe(24)
                admin_insert = text(
                    "INSERT INTO users (username, email, password_hash, role, is_active, created_at, updated_at) "
                    "VALUES (:username, :email, :password_hash, :role, :is_active, datetime('now'), datetime('now'))"
                )
                db.execute(
                    admin_insert,
                    {
                        "username": "admin",
                        "email": "admin@sentinex.gov",
                        "password_hash": hash_password(admin_password),
                        "role": "ADMIN",
                        "is_active": True,
                    },
                )
                db.execute(
                    admin_insert,
                    {
                        "username": "police",
                        "email": "officer@sentinex.gov",
                        "password_hash": hash_password(police_password),
                        "role": "POLICE",
                        "is_active": True,
                    },
                )
                db.commit()
                print("Generated initial passwords for default users:")
                print(f"  admin: {admin_password}")
                print(f"  police: {police_password}")
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
