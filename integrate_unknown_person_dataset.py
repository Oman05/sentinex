"""
Sentinex "Unknown Person" Negative/Distractor Set Integration Script
====================================================================
Registers the local face dataset located at:

    /home/oman/Pictures/unknown person/*.jpg

as a NEGATIVE / DISTRACTOR evaluation set (Option A).

Why this dataset is handled differently
---------------------------------------
"Unknown" identities are the exact opposite of an enrolled identity. Their
scientific purpose is to measure whether the system correctly DECLINES to
match people who are NOT in the gallery (true negatives / false-match-rate).
This mirrors how the existing benchmark handles `unknown_test`
(see integrate_face_dataset.py:  "Negative/un-enrolled probe set -
intentionally not in gallery").

Therefore this script deliberately does NOT:
  - create `cases` rows,
  - create `reference_images` rows,
  - compute or persist `face_embeddings`,
  - add anything to the searchable vector index.

The live MISSING/WANTED gallery is left completely untouched.  Instead it:

1. Copies the images into datasets/negative_sets/unknown_local/ (audit trail).
2. Registers the dataset in `dataset_registry` with category = TEST.
3. Runs an NEGATIVE-SET EVALUATION: every probe image is matched against the
   full live gallery (both MISSING and WANTED scopes).  A probe is a TRUE
   NEGATIVE if its best similarity is below the operational threshold
   (the system correctly rejects it) and a FALSE POSITIVE if it exceeds the
   threshold (the system would raise a spurious alert).
4. Records the run + results in `evaluation_runs` / `evaluation_results`.
5. Writes a per-image score ledger CSV for audit.
6. Synchronizes the SQLite database between root and backend directories.

Usage:
    python integrate_unknown_person_dataset.py
"""

import csv
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# Ensure backend is on PYTHONPATH
SENTINEX_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SENTINEX_ROOT / "backend"))

import app.main  # noqa: E402  (ensure all ORM models are registered)
from app.database.session import SessionLocal, init_db  # noqa: E402
from app.models.reference_image import ReferenceImage  # noqa: E402
from app.models.face_embedding import FaceEmbeddingDB  # noqa: E402
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
SOURCE_DIR = Path("/home/oman/Pictures/unknown person")
DEST_DIR = SENTINEX_ROOT / "datasets" / "negative_sets" / "unknown_local"

# Operational decision threshold (must mirror matching_settings.REVIEW_THRESHOLD)
EVAL_THRESHOLD = 0.70


def run_integration() -> None:
    print("=" * 72)
    print("🚀 Sentinex 'Unknown Person' Negative/Distractor Set Integration")
    print("=" * 72)

    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source dataset directory not found: {SOURCE_DIR}")

    source_files = sorted(
        p for p in SOURCE_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not source_files:
        raise RuntimeError(f"No image files found in {SOURCE_DIR}")
    print(f"\n📂 Found {len(source_files)} probe images in {SOURCE_DIR}")

    init_db()
    db = SessionLocal()

    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            raise RuntimeError("Required seed data (admin user) missing!")

        # --- 1. Copy images for audit trail (NOT enrolled) ------------------
        print("\n📦 1. Archiving probe images (negative set — NOT enrolled)...")
        DEST_DIR.mkdir(parents=True, exist_ok=True)
        copied = 0
        probe_paths: list[Path] = []
        for src_file in source_files:
            dest_file = DEST_DIR / src_file.name
            if not dest_file.exists():
                shutil.copy2(src_file, dest_file)
                copied += 1
            probe_paths.append(dest_file)
        print(f"   ✓ Archived {copied} new images (total {len(probe_paths)}) in {DEST_DIR.relative_to(SENTINEX_ROOT)}")

        # --- 2. Load live gallery from persisted embeddings -----------------
        print("\n🗂️  2. Loading the live MISSING/WANTED gallery from the database...")
        emb_service = FaceEmbeddingService()

        gallery_vectors: list[np.ndarray] = []
        gallery_categories: list[str] = []

        embeddings = (
            db.query(FaceEmbeddingDB).filter(FaceEmbeddingDB.is_active == True).all()  # noqa: E712
        )
        for emb in embeddings:
            ref = (
                db.query(ReferenceImage)
                .filter(ReferenceImage.id == emb.reference_image_id)
                .first()
            )
            if not ref or not ref.is_active:
                continue
            gallery_vectors.append(np.frombuffer(emb.vector_bytes, dtype=np.float32))
            gallery_categories.append(emb.category)

        if not gallery_vectors:
            raise RuntimeError("Live gallery is empty — nothing to evaluate against.")

        gallery_matrix = np.array(gallery_vectors, dtype=np.float32)
        gallery_categories_arr = np.array(gallery_categories)
        n_missing = int((gallery_categories_arr == "MISSING").sum())
        n_wanted = int((gallery_categories_arr == "WANTED").sum())
        print(f"   ✓ Gallery loaded: {len(gallery_vectors)} embeddings ({n_missing} MISSING, {n_wanted} WANTED)")

        # --- 3. Register the negative dataset -------------------------------
        print("\n📊 3. Registering negative dataset in dataset_registry (Module 11)...")
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

        dataset_name = "Local Unknown Person Negative Set (Pictures/unknown person)"
        ds_reg = (
            db.query(DatasetRegistryDB)
            .filter(DatasetRegistryDB.dataset_name == dataset_name)
            .first()
        )
        if not ds_reg:
            ds_reg = DatasetRegistryDB(
                dataset_name=dataset_name,
                dataset_version="1.0",
                category="TEST",
                source_type="LOCAL",
                sample_count=len(probe_paths),
                notes=(
                    f"NEGATIVE / DISTRACTOR probe set supplied from {SOURCE_DIR}. These identities "
                    f"are intentionally NOT enrolled in the gallery. Purpose: measure false-match "
                    f"suppression (true negatives) against the live MISSING/WANTED gallery."
                ),
                creation_date=datetime.utcnow(),
            )
            db.add(ds_reg)
            db.commit()
            db.refresh(ds_reg)
            print(f"   ✓ Registered dataset '{dataset_name}'")
        else:
            print(f"   ✓ Dataset '{dataset_name}' already registered")

        # --- 4. Negative-set evaluation -------------------------------------
        print("\n🔬 4. Running negative-set evaluation against the live gallery...")
        threshold = EVAL_THRESHOLD
        probes_evaluated = 0
        probes_skipped = 0
        true_negatives = 0
        false_positives = 0
        all_best_sims: list[float] = []
        ledger_rows: list[list] = []

        for probe_path in probe_paths:
            bgr = cv2.imread(str(probe_path), cv2.IMREAD_COLOR)
            vec = emb_service.extract_face_embedding(bgr) if bgr is not None else None
            if vec is None:
                probes_skipped += 1
                ledger_rows.append([probe_path.name, "", "", "", "SKIPPED_UNREADABLE"])
                continue

            # Cosine similarity vs every enrolled reference embedding
            sims = np.dot(gallery_matrix, vec)
            max_idx = int(np.argmax(sims))
            best_sim = float(sims[max_idx])
            best_cat = str(gallery_categories_arr[max_idx])

            probes_evaluated += 1
            all_best_sims.append(best_sim)

            if best_sim >= threshold:
                false_positives += 1
                outcome = "FALSE_POSITIVE"
            else:
                true_negatives += 1
                outcome = "TRUE_NEGATIVE"

            ledger_rows.append(
                [probe_path.name, f"{best_sim:.4f}", best_cat, f"{threshold:.2f}", outcome]
            )

        # Negative-set metrics
        fmr = false_positives / probes_evaluated if probes_evaluated > 0 else 0.0
        tnr = true_negatives / probes_evaluated if probes_evaluated > 0 else 0.0
        avg_best_sim = float(np.mean(all_best_sims)) if all_best_sims else 0.0
        max_best_sim = float(np.max(all_best_sims)) if all_best_sims else 0.0
        min_best_sim = float(np.min(all_best_sims)) if all_best_sims else 0.0

        print(f"   • Probes evaluated:      {probes_evaluated}")
        print(f"   • Probes skipped:        {probes_skipped}")
        print(f"   • Operational threshold: {threshold:.2f}")
        print(f"   • True Negatives (TN):   {true_negatives}")
        print(f"   • False Positives (FP):  {false_positives}")
        print(f"   • True Negative Rate:    {tnr:.4f} ({tnr*100:.1f}%)")
        print(f"   • False Match Rate:      {fmr:.4f} ({fmr*100:.1f}%)")
        print(f"   • Best-sim  min/avg/max: {min_best_sim:.4f} / {avg_best_sim:.4f} / {max_best_sim:.4f}")

        # --- 5. Record the evaluation run -----------------------------------
        run_id_str = f"EVAL-LOCALUNK-{int(datetime.utcnow().timestamp())}"
        eval_run = EvaluationRunDB(
            run_id=run_id_str,
            run_name="Local Unknown Person Negative-Set False-Match Evaluation",
            dataset_registry_id=ds_reg.id,
            model_registry_id=model_reg.id,
            model_name=emb_service.model_name,
            model_version=emb_service.model_version,
            dataset_name=ds_reg.dataset_name,
            dataset_version=ds_reg.dataset_version,
            threshold=threshold,
            status="COMPLETED",
            notes=(
                f"Negative/distractor evaluation: {probes_evaluated} un-enrolled 'unknown' probe "
                f"images matched against the live gallery ({len(gallery_vectors)} embeddings). "
                f"A probe is a true negative when its best similarity stays below the threshold."
            ),
            justification="Strict operational point to assess false-match suppression on strangers.",
            created_by_user_id=admin_user.id,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(eval_run)
        db.flush()

        eval_result = EvaluationResultDB(
            run_id=run_id_str,
            # Negative-set evaluation: the meaningful cells are TN (correct
            # rejection) and FP (spurious alert). TP/FN are not applicable
            # because no probe is enrolled.
            true_positives=0,
            false_positives=false_positives,
            true_negatives=true_negatives,
            false_negatives=0,
            precision=None,
            recall=None,
            f1_score=None,
            false_match_rate=round(fmr, 4),
            false_non_match_rate=None,
            top1_accuracy=None,
            top5_retrieval_rate=None,
            average_similarity_score=round(avg_best_sim, 4),
            average_latency_ms=None,
            evaluated_at=datetime.utcnow(),
        )
        db.add(eval_result)
        db.commit()
        print(f"\n   ✓ Recorded evaluation run {run_id_str}")

        # --- 6. Sync SQLite database ----------------------------------------
        backend_db = SENTINEX_ROOT / "backend" / "sentinex.db"
        root_db = SENTINEX_ROOT / "sentinex.db"
        if backend_db.exists() and root_db.exists():
            shutil.copy2(root_db, backend_db)
            print("   ✓ Synchronized SQLite database to backend/sentinex.db")

        # --- 7. Write score ledger ------------------------------------------
        ledger_path = DEST_DIR / "_evaluation_ledger.csv"
        with open(ledger_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["probe_file", "best_similarity", "best_matched_category", "threshold", "outcome"])
            writer.writerows(ledger_rows)
        print(f"   ✓ Score ledger written to {ledger_path.relative_to(SENTINEX_ROOT)}")

        print("\n✅ 'Unknown Person' negative-set integration completed successfully!")
        print("   NOTE: No cases, reference images, or embeddings were added.")
        print("         The live searchable gallery is unchanged.")
        print("=" * 72)
    finally:
        db.close()


if __name__ == "__main__":
    run_integration()
