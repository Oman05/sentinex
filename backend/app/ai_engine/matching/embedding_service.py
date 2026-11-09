"""
Module 7 – Face Embedding Service & Reference Preprocessing Pipeline
=====================================================================
Orchestrates face feature generation, reference image enrollment,
model version verification, and synchronization with the search index.

Preprocessing Pipeline (Section 4):
-----------------------------------
Reference Image -> Quality Validation -> Feature Extraction -> Vector Storage -> Search Index
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.ai_engine.config.matching_settings import matching_settings
from app.ai_engine.matching.models.embedding_model import (
    BaseFaceEmbeddingModel,
    get_embedding_model,
)
from app.ai_engine.matching.vector_search import vector_search_index
from app.ai_engine.quality.image_validator import FaceImageValidator, ImageValidationStatus
from app.ai_engine.schemas.matching import (
    ReferenceEmbeddingRecord,
    ReindexResponse,
)
from app.models.case import Case, CaseStatus
from app.models.reference_image import ReferenceImage

logger = logging.getLogger(__name__)


class FaceEmbeddingService:
    """
    Service responsible for extracting, validating, persisting,
    and managing facial feature embeddings.
    """

    def __init__(self, model: BaseFaceEmbeddingModel | None = None) -> None:
        self.model = model or get_embedding_model()

    @property
    def model_name(self) -> str:
        return self.model.model_name

    @property
    def model_version(self) -> str:
        return self.model.model_version

    @property
    def embedding_dim(self) -> int:
        return self.model.embedding_dim

    def extract_face_embedding(self, image_input: Any) -> np.ndarray | None:
        """
        Validates, decodes, and generates a normalized embedding vector
        from an image array, file path, bytes, or base64 string.
        """
        if image_input is None:
            return None

        # 1. Decode and validate image
        val, val_status = FaceImageValidator.validate(image_input)
        if val_status != ImageValidationStatus.VALID or val is None:
            logger.warning("[EmbeddingService] Image validation failed: %s", val_status)
            return None

        # 2. Extract L2-normalized feature representation
        try:
            return self.model.extract_embedding(val.image_bgr)
        except Exception as exc:
            logger.error("[EmbeddingService] Feature extraction error: %s", exc)
            return None

    def enroll_reference_image(
        self,
        reference_image: ReferenceImage,
        case: Case,
        db: Session | None = None,
    ) -> ReferenceEmbeddingRecord | None:
        """
        Processes an enrolled reference image, computes its feature vector,
        persists metadata to the database, and adds it to the vector search index.
        """
        # Ensure case and image are active
        if matching_settings.REQUIRE_ACTIVE_CASES_ONLY:
            if not case.is_active or case.status not in {CaseStatus.ACTIVE.value, "ACTIVE"}:
                logger.debug("[EmbeddingService] Skipping non-active case %s", case.case_number)
                return None

        if matching_settings.REQUIRE_ACTIVE_IMAGES_ONLY:
            if not reference_image.is_active:
                logger.debug("[EmbeddingService] Skipping inactive image %s", reference_image.id)
                return None

        # Check for valid cached embedding in database first to avoid redundant extraction
        vector = None
        if db is not None:
            try:
                from app.models.face_embedding import FaceEmbeddingDB
                cached = (
                    db.query(FaceEmbeddingDB)
                    .filter(
                        FaceEmbeddingDB.reference_image_id == reference_image.id,
                        FaceEmbeddingDB.model_name == self.model_name,
                        FaceEmbeddingDB.model_version == self.model_version,
                        FaceEmbeddingDB.is_active == True,
                    )
                    .first()
                )
                if cached and cached.vector_bytes:
                    vector = np.frombuffer(cached.vector_bytes, dtype=np.float32)
            except Exception as cache_err:
                logger.debug("[EmbeddingService] Cache lookup error: %s", cache_err)

        # If not cached, extract feature vector from file path or storage reference
        if vector is None:
            vector = self.extract_face_embedding(reference_image.file_path)

        if vector is None:
            logger.warning(
                "[EmbeddingService] Failed to extract features from reference %s (%s)",
                reference_image.id,
                reference_image.file_path,
            )
            return None

        # Build embedding record
        record = ReferenceEmbeddingRecord(
            image_id=reference_image.id,
            case_id=case.id,
            case_number=case.case_number,
            category=case.category,
            department_id=case.department_id,
            model_name=self.model_name,
            model_version=self.model_version,
            embedding_dim=self.embedding_dim,
            is_active=True,
            reference_quality_score=0.90 if reference_image.is_primary else 0.80,
        )

        # Update search index
        vector_search_index.add_embedding(record, vector)

        # Persist to face_embeddings database table if db session provided
        if db is not None and matching_settings.PERSIST_EMBEDDINGS:
            self._persist_embedding(db, record, vector)

        return record

    def _persist_embedding(
        self,
        db: Session,
        record: ReferenceEmbeddingRecord,
        vector: np.ndarray,
    ) -> None:
        """Saves embedding vector bytes and metadata into face_embeddings table."""
        try:
            from app.models.face_embedding import FaceEmbeddingDB

            existing = (
                db.query(FaceEmbeddingDB)
                .filter(FaceEmbeddingDB.reference_image_id == record.image_id)
                .first()
            )
            vec_bytes = vector.astype(np.float32).tobytes()

            if existing:
                existing.case_id = record.case_id
                existing.category = record.category
                existing.model_name = record.model_name
                existing.model_version = record.model_version
                existing.embedding_dim = record.embedding_dim
                existing.vector_bytes = vec_bytes
                existing.is_active = record.is_active
            else:
                db_row = FaceEmbeddingDB(
                    reference_image_id=record.image_id,
                    case_id=record.case_id,
                    category=record.category,
                    embedding_reference=record.embedding_id,
                    model_name=record.model_name,
                    model_version=record.model_version,
                    embedding_dim=record.embedding_dim,
                    vector_bytes=vec_bytes,
                    is_active=record.is_active,
                )
                db.add(db_row)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("[EmbeddingService] DB write error for embedding: %s", exc)

    def reindex_all_reference_images(self, db: Session) -> ReindexResponse:
        """
        Scans all active cases and reference images in the database,
        computes fresh embeddings using the active model, and refreshes the search index.
        """
        start_time = time.perf_counter()
        vector_search_index.clear()

        # Query all active cases
        cases = (
            db.query(Case)
            .filter(Case.is_active == True, Case.status.in_([CaseStatus.ACTIVE.value, "ACTIVE"]))
            .all()
        )

        scanned = 0
        enrolled = 0
        errors = 0

        for case in cases:
            # Query active reference images for this case
            images = (
                db.query(ReferenceImage)
                .filter(ReferenceImage.case_id == case.id, ReferenceImage.is_active == True)
                .all()
            )
            for img in images:
                scanned += 1
                try:
                    res = self.enroll_reference_image(img, case, db=db)
                    if res is not None:
                        enrolled += 1
                    else:
                        errors += 1
                except Exception as exc:
                    errors += 1
                    logger.error("[EmbeddingService] Reindex error on image %s: %s", img.id, exc)

        duration = round(time.perf_counter() - start_time, 3)
        logger.info(
            "[EmbeddingService] Re-indexing complete: %d scanned, %d enrolled, %d errors in %.2fs",
            scanned,
            enrolled,
            errors,
            duration,
        )

        return ReindexResponse(
            status="COMPLETED",
            total_reference_images_scanned=scanned,
            embeddings_generated=enrolled,
            embeddings_deactivated=0,
            errors_encountered=errors,
            model_name=self.model_name,
            model_version=self.model_version,
            duration_s=duration,
        )


# Module-level singleton
embedding_service = FaceEmbeddingService()
