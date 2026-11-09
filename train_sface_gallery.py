#!/usr/bin/env python3
'''Recompute active reference-image embeddings with pretrained OpenCV SFace.'''
from __future__ import annotations
import hashlib
import sys
import time
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
import app.main  # noqa: F401
from app.database.session import SessionLocal
from app.ai_engine.matching.models.embedding_model import get_embedding_model
from app.models.analytics import ModelRegistryDB
from app.models.case import Case
from app.models.face_embedding import FaceEmbeddingDB
from app.models.reference_image import ReferenceImage

def main() -> None:
    model = get_embedding_model("OPENCV_SFACE")
    db = SessionLocal()
    started = time.time()
    updated = skipped = 0
    try:
        rows = (
            db.query(FaceEmbeddingDB, ReferenceImage, Case)
            .join(ReferenceImage, ReferenceImage.id == FaceEmbeddingDB.reference_image_id)
            .join(Case, Case.id == FaceEmbeddingDB.case_id)
            .filter(FaceEmbeddingDB.is_active.is_(True), ReferenceImage.is_active.is_(True), Case.is_active.is_(True))
            .all()
        )
        print(f"Re-embedding {len(rows)} active references with {model.model_name} v{model.model_version}...")
        for i, (embedding, image, case) in enumerate(rows, 1):
            frame = cv2.imread(image.file_path, cv2.IMREAD_COLOR)
            if frame is None:
                skipped += 1
                print(f"SKIP {image.id}: cannot read image ({image.file_path})")
                continue
            try:
                vector = model.extract_embedding(frame)
            except ValueError as exc:
                skipped += 1
                print(f"SKIP {image.id}: {exc}")
                continue
            if vector is None or not np.isfinite(vector).all() or np.linalg.norm(vector) < 1e-8:
                skipped += 1
                print(f"SKIP {image.id}: no valid face embedding ({image.file_path})")
                continue
            embedding.model_name = model.model_name
            embedding.model_version = model.model_version
            embedding.embedding_dim = model.embedding_dim
            embedding.vector_bytes = vector.astype(np.float32).tobytes()
            updated += 1
            if i % 25 == 0:
                db.commit()
                print(f"  processed {i}/{len(rows)}; embedded={updated}; skipped={skipped}")
        db.commit()
        reg = db.query(ModelRegistryDB).filter(ModelRegistryDB.model_name == model.model_name).first()
        if not reg:
            reg = ModelRegistryDB(
                model_name=model.model_name,
                model_type="FACE_EMBEDDING",
                version=model.model_version,
                framework="OpenCV DNN / SFace ONNX",
                checksum=hashlib.sha256((ROOT / "backend/face_recognition_sface_2021dec.onnx").read_bytes()).hexdigest(),
                status="ACTIVE",
                notes="Pretrained OpenCV SFace face-recognition model with YuNet face alignment. Evaluated on held-out LFW-derived 150-identity benchmark; threshold must be set via validation.",
            )
            db.add(reg)
        else:
            reg.version = model.model_version
            reg.framework = "OpenCV DNN / SFace ONNX"
            reg.checksum = hashlib.sha256((ROOT / "backend/face_recognition_sface_2021dec.onnx").read_bytes()).hexdigest()
            reg.status = "ACTIVE"
            reg.notes = "Pretrained OpenCV SFace face-recognition model with YuNet face alignment. Evaluated on held-out LFW-derived 150-identity benchmark; threshold must be set via validation."
        db.commit()
        print(f"DONE: embedded={updated}, skipped={skipped}, elapsed={time.time()-started:.1f}s")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
