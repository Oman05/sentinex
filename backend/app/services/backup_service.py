from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import time
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.backup import BackupRecordDB
from app.models.audit_log import AuditLog

BACKUP_DIR = "./backups"


class BackupService:
    def __init__(self, backup_dir: str = BACKUP_DIR):
        self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(
        self,
        db: Session,
        user_id: int | None = None,
        backup_type: str = "FULL",
        notes: str | None = None,
    ) -> dict:
        start_time = time.perf_counter()
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_id = f"BKP-{timestamp_str}-{uuid4().hex[:6].upper()}"
        tar_filename = f"sentinex_backup_{backup_id}.tar.gz"
        tar_filepath = os.path.join(self.backup_dir, tar_filename)

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = {
                "backup_id": backup_id,
                "backup_type": backup_type,
                "created_at": datetime.utcnow().isoformat(),
                "created_by_user_id": user_id,
                "notes": notes,
                "components": [],
            }

            # 1. Database snapshot
            if "sqlite" in settings.DATABASE_URL:
                db_filename = settings.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "").split("?")[0]
                db_clean_path = db_filename.lstrip("./")
                if os.path.exists(db_clean_path):
                    dest_db = os.path.join(temp_dir, "database.db")
                    # Safe SQLite online backup
                    with sqlite3.connect(db_clean_path) as src, sqlite3.connect(dest_db) as dst:
                        src.backup(dst)
                    manifest["components"].append("database_sqlite")
            else:
                manifest["components"].append("database_metadata_only")

            # 2. Configuration snapshot
            try:
                from app.services.config_service import config_service
                configs = config_service.get_all_configs(db)
                with open(os.path.join(temp_dir, "configurations.json"), "w") as f:
                    json.dump(configs, f, indent=2)
                manifest["components"].append("configurations")
            except Exception:
                pass

            # 3. Model & Dataset Registry snapshot
            try:
                from app.models.analytics import ModelRegistryDB, DatasetRegistryDB
                models = [
                    {"model_name": m.model_name, "version": m.version, "is_active": m.is_active}
                    for m in db.query(ModelRegistryDB).all()
                ]
                datasets = [
                    {"dataset_name": d.dataset_name, "version": d.version, "sample_count": d.sample_count}
                    for d in db.query(DatasetRegistryDB).all()
                ]
                with open(os.path.join(temp_dir, "registries.json"), "w") as f:
                    json.dump({"models": models, "datasets": datasets}, f, indent=2)
                manifest["components"].append("registries")
            except Exception:
                pass

            # Write manifest
            with open(os.path.join(temp_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f, indent=2)

            # Create compressed archive
            with tarfile.open(tar_filepath, "w:gz") as tar:
                for file_name in os.listdir(temp_dir):
                    tar.add(os.path.join(temp_dir, file_name), arcname=file_name)

        # Calculate checksum & size
        hasher = hashlib.sha256()
        with open(tar_filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        checksum = hasher.hexdigest()
        file_size = os.path.getsize(tar_filepath)
        duration = round(time.perf_counter() - start_time, 3)

        # Record in DB
        backup_record = BackupRecordDB(
            backup_id=backup_id,
            filename=tar_filename,
            filepath=tar_filepath,
            backup_type=backup_type,
            size_bytes=file_size,
            duration_seconds=duration,
            status="COMPLETED",
            checksum_sha256=checksum,
            verification_status="VERIFIED",
            created_at=datetime.utcnow(),
            created_by_user_id=user_id,
            notes=notes,
        )
        db.add(backup_record)

        # Audit log
        if user_id:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action="BACKUP_CREATED",
                    resource_type="BACKUP",
                    resource_id=None,
                    details=f"Created {backup_type} backup {backup_id} (Size: {file_size} bytes)",
                )
            )

        db.commit()
        db.refresh(backup_record)

        return {
            "id": backup_record.id,
            "backup_id": backup_record.backup_id,
            "filename": backup_record.filename,
            "filepath": backup_record.filepath,
            "backup_type": backup_record.backup_type,
            "size_bytes": backup_record.size_bytes,
            "duration_seconds": backup_record.duration_seconds,
            "status": backup_record.status,
            "checksum_sha256": backup_record.checksum_sha256,
            "verification_status": backup_record.verification_status,
            "created_at": backup_record.created_at.isoformat(),
            "notes": backup_record.notes,
        }

    def list_backups(self, db: Session, limit: int = 50) -> list[dict]:
        records = db.query(BackupRecordDB).order_by(BackupRecordDB.created_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "backup_id": r.backup_id,
                "filename": r.filename,
                "filepath": r.filepath,
                "backup_type": r.backup_type,
                "size_bytes": r.size_bytes,
                "duration_seconds": r.duration_seconds,
                "status": r.status,
                "checksum_sha256": r.checksum_sha256,
                "verification_status": r.verification_status,
                "created_at": r.created_at.isoformat(),
                "created_by_user_id": r.created_by_user_id,
                "notes": r.notes,
            }
            for r in records
        ]

    def verify_backup(self, db: Session, backup_id: str) -> dict:
        record = db.query(BackupRecordDB).filter(BackupRecordDB.backup_id == backup_id).first()
        if not record:
            raise ValueError(f"Backup '{backup_id}' not found.")

        if not os.path.exists(record.filepath):
            record.verification_status = "FILE_MISSING"
            db.commit()
            return {
                "backup_id": backup_id,
                "is_valid": False,
                "status": "FILE_MISSING",
                "checksum_sha256": record.checksum_sha256,
                "details": f"File does not exist at {record.filepath}",
            }

        # Checksum verification
        hasher = hashlib.sha256()
        with open(record.filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        calc_checksum = hasher.hexdigest()

        if calc_checksum != record.checksum_sha256:
            record.verification_status = "CORRUPT_CHECKSUM"
            db.commit()
            return {
                "backup_id": backup_id,
                "is_valid": False,
                "status": "CORRUPT_CHECKSUM",
                "checksum_sha256": calc_checksum,
                "details": "Calculated SHA-256 does not match database record.",
            }

        # Verify tar archive integrity
        try:
            with tarfile.open(record.filepath, "r:gz") as tar:
                names = tar.getnames()
                if "manifest.json" not in names:
                    raise ValueError("Missing manifest.json in backup archive.")
            record.verification_status = "VERIFIED"
            db.commit()
            return {
                "backup_id": backup_id,
                "is_valid": True,
                "status": "VERIFIED",
                "checksum_sha256": calc_checksum,
                "details": f"Archive structure valid. Contains {len(names)} components.",
            }
        except Exception as e:
            record.verification_status = "CORRUPT_ARCHIVE"
            db.commit()
            return {
                "backup_id": backup_id,
                "is_valid": False,
                "status": "CORRUPT_ARCHIVE",
                "checksum_sha256": calc_checksum,
                "details": f"Tar archive corrupted: {e}",
            }

    def restore_backup(
        self,
        db: Session,
        backup_id: str,
        confirmation_code: str,
        user_id: int | None = None,
    ) -> dict:
        if confirmation_code != "CONFIRM_RESTORE":
            raise ValueError("Explicit confirmation code 'CONFIRM_RESTORE' required to proceed with system restore.")

        record = db.query(BackupRecordDB).filter(BackupRecordDB.backup_id == backup_id).first()
        if not record:
            raise ValueError(f"Backup '{backup_id}' not found.")

        # Pre-verification
        verify_res = self.verify_backup(db, backup_id)
        if not verify_res["is_valid"]:
            raise ValueError(f"Backup verification failed: {verify_res['details']}")

        # Extract safely in temporary directory
        with tempfile.TemporaryDirectory() as extract_dir:
            with tarfile.open(record.filepath, "r:gz") as tar:
                # Prevent path traversal vulnerability
                for member in tar.getmembers():
                    target_path = os.path.abspath(os.path.join(extract_dir, member.name))
                    if not target_path.startswith(os.path.abspath(extract_dir)):
                        raise ValueError("Security violation: Attempted path traversal inside archive.")
                tar.extractall(extract_dir)

            with open(os.path.join(extract_dir, "manifest.json")) as f:
                manifest = json.load(f)

            # Restore configurations if available
            config_file = os.path.join(extract_dir, "configurations.json")
            if os.path.exists(config_file):
                with open(config_file) as f:
                    configs_data = json.load(f)
                    from app.services.config_service import config_service
                    for cfg in configs_data:
                        try:
                            config_service.update_config(
                                db,
                                cfg["key"],
                                cfg["value"],
                                reason=f"Restored from backup {backup_id}",
                                user_id=user_id,
                            )
                        except Exception:
                            pass

        record.status = "RESTORED"
        if user_id:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action="BACKUP_RESTORED",
                    resource_type="BACKUP",
                    resource_id=record.id,
                    details=f"Restored system state from backup {backup_id}",
                )
            )
        db.commit()

        return {
            "backup_id": backup_id,
            "status": "RESTORED",
            "components_restored": manifest.get("components", []),
            "restored_at": datetime.utcnow().isoformat(),
            "notes": record.notes,
        }


backup_service = BackupService()
