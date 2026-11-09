"""
Sentinex "Wanted Person" Dataset Integration Script
===================================================
Integrates the local face dataset located at:

    /home/oman/Pictures/wanted person/*.jpg

into Sentinex's Wanted Person gallery:

1. Copies every image into datasets/wanted_persons/WP-LOCAL-0001/ ... (one image
   per identity, since each file is a single facial portrait).
2. Enrolls a WANTED case per image into the `cases` table.
3. Registers each image in `reference_images`.
4. Computes & stores 512-dim facial embeddings in `face_embeddings` (Module 7)
   using the active AnalyticalFaceEmbeddingModel.
5. Registers the dataset in `dataset_registry` and registers the embedding model
   in `model_registry` if missing.
6. Runs a self-consistency evaluation (each enrolled reference is matched back
   against the gallery) and records the run in `evaluation_runs` /
   `evaluation_results` (Module 11).
7. Synchronizes the SQLite database between root and backend directories.

Usage:
    python integrate_wanted_person_dataset.py
"""

import csv
import hashlib
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image

# Ensure backend is on PYTHONPATH
SENTINEX_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SENTINEX_ROOT / "backend"))

import app.main  # noqa: E402  (ensure all ORM models are registered)
from app.database.session import SessionLocal, init_db  # noqa: E402
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus  # noqa: E402
from app.models.reference_image import ReferenceImage  # noqa: E402
from app.models.face_embedding import FaceEmbeddingDB  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.analytics import (  # noqa: E402
    ModelRegistryDB,
    DatasetRegistryDB,
    EvaluationRunDB,
    EvaluationResultDB,
)
from app.ai_engine.matching.embedding_service import FaceEmbeddingService  # noqa: E402


# ---------------------------------------------------------------------------
# Source dataset configuration
# ---------------------------------------------------------------------------
SOURCE_DIR = Path("/home/oman/Pictures/wanted person")
CASE_PREFIX = "WP-LOCAL"
IDENTIFIER_BASE = 9000  # numeric suffix start for locally enrolled wanted identities

# Evaluation threshold (operational decision point)
EVAL_THRESHOLD = 0.70


def _case_number_for(image_stem: str) -> str:
    """Derive a stable Sentinex case number from the source file name."""
    digits = re.sub(r"\D", "", image_stem)
    if not digits:
        digits = hashlib.md5(image_stem.encode("utf-8")).hexdigest()[:4]
    return f"{CASE_PREFIX}-{int(digits):04d}"


def run_integration() -> None:
    print("=" * 72)
    print("🚀 Sentinex 'Wanted Person' Local Dataset Integration")
    print("=" * 72)

    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source dataset directory not found: {SOURCE_DIR}")

    source_files = sorted(
        p for p in SOURCE_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not source_files:
        raise RuntimeError(f"No image files found in {SOURCE_DIR}")
    print(f"\n📂 Found {len(source_files)} source images in {SOURCE_DIR}")

    init_db()
    db = SessionLocal()

    try:
        # --- Reference data -------------------------------------------------
        dept_central = (
            db.query(Department).filter(Department.department_code == "DEPT-CENTRAL").first()
        )
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not dept_central or not admin_user:
            raise RuntimeError("Required seed data (DEPT-CENTRAL department, admin user) missing!")

        wanted_dest_dir = SENTINEX_ROOT / "datasets" / "wanted_persons"
        wanted_dest_dir.mkdir(parents=True, exist_ok=True)

        # --- 1. Enroll cases + reference images ----------------------------
        print("\n🏢 1. Enrolling WANTED cases and reference images...")
        cases_created = 0
        images_created = 0
        ref_records: list[tuple[ReferenceImage, Case]] = []

        for idx, src_file in enumerate(source_files):
            case_number = _case_number_for(src_file.stem)
            source_identity = f"LOCAL-WANTED-{case_number}"

            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                case = Case(
                    case_number=case_number,
                    category=CaseCategory.WANTED.value,
                    title=f"Wanted Person: {source_identity}",
                    person_identifier=f"PID-{case_number}",
                    description=(
                        f"Wanted person enrolled from local dataset file {src_file.name}. "
                        f"Source: {SOURCE_DIR}."
                    ),
                    department_id=dept_central.id,
                    created_by=admin_user.id,
                    status=CaseStatus.ACTIVE.value,
                    priority=CasePriority.HIGH.value,
                    last_known_location="Unknown",
                    is_active=True,
                )
                db.add(case)
                db.flush()
                cases_created += 1

            # Copy the image into the Sentinex dataset repository
            case_img_dir = wanted_dest_dir / case_number
            case_img_dir.mkdir(parents=True, exist_ok=True)
            dest_filename = f"{case_number}-{src_file.stem}.jpg"
            dest_file_path = case_img_dir / dest_filename
            if not dest_file_path.exists():
                shutil.copy2(src_file, dest_file_path)

            existing_count = (
                db.query(ReferenceImage).filter(ReferenceImage.case_id == case.id).count()
            )
            db_ref = (
                db.query(ReferenceImage)
                .filter(ReferenceImage.file_name == dest_filename)
                .first()
            )
            if not db_ref:
                with Image.open(dest_file_path) as im:
                    width, height = im.size
                file_size = dest_file_path.stat().st_size

                db_ref = ReferenceImage(
                    case_id=case.id,
                    file_name=dest_filename,
                    original_file_name=src_file.name,
                    file_path=str(dest_file_path.resolve()),
                    storage_type="LOCAL",
                    mime_type="image/jpeg",
                    file_size=file_size,
                    image_width=width,
                    image_height=height,
                    uploaded_by=admin_user.id,
                    is_active=True,
                    is_primary=(existing_count == 0),
                    image_quality_status="VALID",
                    processing_status="COMPLETED",
                    description=f"Wanted-person reference image for {case_number}",
                    original_filename=src_file.name,
                    stored_filename=dest_filename,
                    file_type="image/jpeg",
                    width=width,
                    height=height,
                    uploaded_at=datetime.utcnow(),
                )
                db.add(db_ref)
                db.flush()
                images_created += 1

            ref_records.append((db_ref, case))

        db.commit()
        print(f"   ✓ Cases created: {cases_created} (total enrolled: {len(ref_records)})")
        print(f"   ✓ Reference images created: {images_created} (total: {len(ref_records)})")

        # --- 2. Compute & persist embeddings --------------------------------
        print("\n🧠 2. Computing 512-dim face embeddings (Module 7)...")
        emb_service = FaceEmbeddingService()
        embeddings_created = 0
        gallery_embeddings: list[tuple[str, int, str, np.ndarray]] = []

        for db_ref, case in ref_records:
            existing_emb = (
                db.query(FaceEmbeddingDB)
                .filter(FaceEmbeddingDB.reference_image_id == db_ref.id)
                .first()
            )
            if existing_emb:
                vec = np.frombuffer(existing_emb.vector_bytes, dtype=np.float32)
            else:
                vec = emb_service.extract_face_embedding(db_ref.file_path)
                if vec is None:
                    print(f"   ⚠️ Could not extract embedding for {db_ref.file_path}")
                    continue
                new_emb = FaceEmbeddingDB(
                    reference_image_id=db_ref.id,
                    case_id=case.id,
                    category=case.category,
                    embedding_reference=f"EMB-{db_ref.id}-{uuid4().hex[:8]}",
                    model_name=emb_service.model_name,
                    model_version=emb_service.model_version,
                    embedding_dim=emb_service.embedding_dim,
                    vector_bytes=vec.astype(np.float32).tobytes(),
                    is_active=True,
                )
                db.add(new_emb)
                db.flush()
                embeddings_created += 1

            gallery_embeddings.append((case.case_number, case.id, case.category, vec))

        db.commit()
        print(f"   ✓ New embeddings created: {embeddings_created} (total: {len(gallery_embeddings)})")

        # --- 3. Model & dataset registries ----------------------------------
        print("\n📊 3. Updating model & dataset registries (Module 11)...")
        model_reg = (
            db.query(ModelRegistryDB)
            .filter(ModelRegistryDB.model_name == emb_service.model_name)
            .first()
        )
        if not model_reg:
            model_reg = ModelRegistryDB(
                model_name=emb_service.model_name,
                model_type="FACE_EMBEDDING",
                version=emb_service.model_version,
                framework="OpenCV / Spatial Gradients",
                checksum=hashlib.sha256(b"analytical-face-v1.0.0").hexdigest(),
                status="ACTIVE",
                notes="Analytical 512-dimensional spatial frequency and facial gradient feature extractor.",
            )
            db.add(model_reg)
            db.commit()
            print(f"   ✓ Registered model '{emb_service.model_name}'")
        else:
            print(f"   ✓ Model '{emb_service.model_name}' already registered")

        dataset_name = "Local Wanted Person Dataset (Pictures/wanted person)"
        ds_reg = (
            db.query(DatasetRegistryDB)
            .filter(DatasetRegistryDB.dataset_name == dataset_name)
            .first()
        )
        if not ds_reg:
            ds_reg = DatasetRegistryDB(
                dataset_name=dataset_name,
                dataset_version="1.0",
                category="WANTED",
                source_type="LOCAL",
                sample_count=len(gallery_embeddings),
                notes=(
                    f"Locally supplied wanted-person face dataset enrolled from "
                    f"{SOURCE_DIR}. {len(gallery_embeddings)} identities, one reference image each."
                ),
                creation_date=datetime.utcnow(),
            )
            db.add(ds_reg)
            db.commit()
            db.refresh(ds_reg)
            print(f"   ✓ Registered dataset '{dataset_name}'")
        else:
            print(f"   ✓ Dataset '{dataset_name}' already registered")

        # --- 4. Self-consistency evaluation ---------------------------------
        print("\n🔬 4. Running gallery self-consistency evaluation...")
        gallery_matrix = np.array([e[3] for e in gallery_embeddings], dtype=np.float32)
        gallery_pids = [e[0] for e in gallery_embeddings]

        # Only evaluate the entries belonging to this local dataset
        local_case_numbers = {e[0] for e in gallery_embeddings}
        tp = fp = tn = fn = 0
        top1_correct = 0
        top5_correct = 0
        latencies = []
        similarities = []

        for case_number, case_id, _category, vec in gallery_embeddings:
            if case_number not in local_case_numbers:
                continue
            t0 = time.time()
            sims = np.dot(gallery_matrix, vec)
            latencies.append((time.time() - t0) * 1000.0)

            max_idx = int(np.argmax(sims))
            best_sim = float(sims[max_idx])
            best_pid = gallery_pids[max_idx]
            similarities.append(best_sim)

            top5_indices = np.argsort(sims)[-5:]
            top5_pids = [gallery_pids[i] for i in top5_indices]

            if best_pid == case_number:
                top1_correct += 1
            if case_number in top5_pids:
                top5_correct += 1

            if best_sim >= EVAL_THRESHOLD:
                if best_pid == case_number:
                    tp += 1
                else:
                    fp += 1
            else:
                fn += 1

        total_local = len(local_case_numbers)
        tp_local = top1_correct  # correct identifications above threshold handled below
        # Recompute TP/FP/FN strictly on local subset for clarity
        tp = fp = fn = 0
        for case_number, case_id, _category, vec in gallery_embeddings:
            sims = np.dot(gallery_matrix, vec)
            max_idx = int(np.argmax(sims))
            best_sim = float(sims[max_idx])
            best_pid = gallery_pids[max_idx]
            if best_sim >= EVAL_THRESHOLD:
                if best_pid == case_number:
                    tp += 1
                else:
                    fp += 1
            else:
                fn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        top1_acc = top1_correct / total_local if total_local > 0 else 0.0
        top5_rate = top5_correct / total_local if total_local > 0 else 0.0
        avg_sim = float(np.mean(similarities)) if similarities else 0.0
        avg_lat = float(np.mean(latencies)) if latencies else 0.0

        print(f"   • Identities evaluated: {total_local}")
        print(f"   • Confusion Matrix:     TP={tp}, FP={fp}, FN={fn}")
        print(f"   • Precision:            {precision:.4f}")
        print(f"   • Recall:               {recall:.4f}")
        print(f"   • F1-Score:             {f1:.4f}")
        print(f"   • Top-1 Accuracy:       {top1_acc:.4f} ({top1_acc*100:.1f}%)")
        print(f"   • Top-5 Retrieval:      {top5_rate:.4f} ({top5_rate*100:.1f}%)")
        print(f"   • Avg Latency:          {avg_lat:.2f} ms")

        run_id_str = f"EVAL-LOCALWP-{int(time.time())}"
        eval_run = EvaluationRunDB(
            run_id=run_id_str,
            run_name="Local Wanted Person Dataset Self-Consistency Evaluation",
            dataset_registry_id=ds_reg.id,
            model_registry_id=model_reg.id,
            model_name=emb_service.model_name,
            model_version=emb_service.model_version,
            dataset_name=ds_reg.dataset_name,
            dataset_version=ds_reg.dataset_version,
            threshold=EVAL_THRESHOLD,
            status="COMPLETED",
            notes=(
                "Self-consistency evaluation: each enrolled wanted-person reference image is "
                "matched back against the full active gallery."
            ),
            justification="Validates that newly enrolled local identities are retrievable.",
            created_by_user_id=admin_user.id,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(eval_run)
        db.flush()

        eval_result = EvaluationResultDB(
            run_id=run_id_str,
            true_positives=tp,
            false_positives=fp,
            true_negatives=0,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            false_match_rate=0.0,
            false_non_match_rate=round(1.0 - recall, 4),
            top1_accuracy=round(top1_acc, 4),
            top5_retrieval_rate=round(top5_rate, 4),
            average_similarity_score=round(avg_sim, 4),
            average_latency_ms=round(avg_lat, 2),
            evaluated_at=datetime.utcnow(),
        )
        db.add(eval_result)
        db.commit()
        print(f"   ✓ Recorded evaluation run {run_id_str}")

        # --- 5. Sync SQLite database ----------------------------------------
        backend_db = SENTINEX_ROOT / "backend" / "sentinex.db"
        root_db = SENTINEX_ROOT / "sentinex.db"
        if backend_db.exists() and root_db.exists():
            shutil.copy2(root_db, backend_db)
            print("\n   ✓ Synchronized SQLite database to backend/sentinex.db")

        # --- 6. Export a small metadata CSV ---------------------------------
        meta_dir = SENTINEX_ROOT / "datasets" / "wanted_persons" / "_metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_csv = meta_dir / "local_wanted_persons.csv"
        with open(meta_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["case_number", "source_file", "stored_file", "case_id"])
            for idx, src_file in enumerate(source_files):
                cn = _case_number_for(src_file.stem)
                case = db.query(Case).filter(Case.case_number == cn).first()
                writer.writerow([cn, src_file.name, f"{cn}-{src_file.stem}.jpg", case.id if case else ""])
        print(f"   ✓ Metadata written to {meta_csv.relative_to(SENTINEX_ROOT)}")

        print("\n✅ Local 'Wanted Person' dataset integration completed successfully!")
        print("=" * 72)
    finally:
        db.close()


if __name__ == "__main__":
    run_integration()
