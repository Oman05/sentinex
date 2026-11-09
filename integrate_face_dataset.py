"""
Sentinex Face Dataset Integration Script
========================================
Integrates the generated 150-identity LFW research dataset into Sentinex:
1. Copies reference images into Sentinex's official dataset repositories:
   - datasets/missing_persons/MP-TEST-XXXX/
   - datasets/wanted_persons/WP-TEST-XXXX/
2. Copies full benchmark evaluation package (including probes & metadata) to:
   - datasets/benchmarks/face_dataset_150/
3. Enrolls the 100 cases (50 Missing + 50 Wanted) into Sentinex database (cases table).
4. Registers all 200 reference images into reference_images table.
5. Computes & stores 512-dim facial embeddings in face_embeddings table (Module 7).
6. Registers the benchmark dataset in dataset_registry (Module 11).
7. Registers the active embedding model in model_registry if missing.
8. Executes a benchmark evaluation run against test probe images, recording
   scientific confusion matrix & metrics into evaluation_runs and evaluation_results.
9. Syncs SQLite database between root and backend directory.
"""

import os
import sys
import shutil
import hashlib
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import csv
import numpy as np
from PIL import Image

# Ensure backend is on PYTHONPATH
SENTINEX_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SENTINEX_ROOT / "backend"))

import app.main  # Ensure all ORM models are registered
from app.database.session import SessionLocal, init_db
from app.models.case import Case, CaseCategory, CasePriority, CaseStatus
from app.models.reference_image import ReferenceImage
from app.models.face_embedding import FaceEmbeddingDB
from app.models.department import Department
from app.models.user import User
from app.models.analytics import (
    ModelRegistryDB,
    DatasetRegistryDB,
    EvaluationRunDB,
    EvaluationResultDB,
)
from app.ai_engine.matching.embedding_service import FaceEmbeddingService


DATASET_PKG_DIR = Path("/home/oman/Downloads/face_dataset_150_package (3)/dataset")


def run_integration():
    print("=" * 70)
    print("🚀 Sentinex 150-Person Face Dataset Integration")
    print("=" * 70)

    if not DATASET_PKG_DIR.exists():
        raise FileNotFoundError(f"Source dataset directory not found: {DATASET_PKG_DIR}")

    init_db()
    db = SessionLocal()

    # 1. Fetch Department & Admin User references
    dept_missing = db.query(Department).filter(Department.department_code == "DEPT-MISSING").first()
    dept_central = db.query(Department).filter(Department.department_code == "DEPT-CENTRAL").first()
    admin_user = db.query(User).filter(User.username == "admin").first()

    if not dept_missing or not dept_central or not admin_user:
        raise RuntimeError("Required seed data (departments, admin user) missing in database!")

    # 2. Setup destination directories
    sentinex_datasets_root = SENTINEX_ROOT / "datasets"
    missing_dest_dir = sentinex_datasets_root / "missing_persons"
    wanted_dest_dir = sentinex_datasets_root / "wanted_persons"
    benchmark_dest_dir = sentinex_datasets_root / "benchmarks" / "face_dataset_150"

    missing_dest_dir.mkdir(parents=True, exist_ok=True)
    wanted_dest_dir.mkdir(parents=True, exist_ok=True)
    benchmark_dest_dir.mkdir(parents=True, exist_ok=True)

    print("\n📦 1. Copying full benchmark dataset into Sentinex repository...")
    for item in ["metadata", "missing_test", "wanted_test", "unknown_test"]:
        s_src = DATASET_PKG_DIR / item
        s_dst = benchmark_dest_dir / item
        if s_src.exists() and not s_dst.exists():
            shutil.copytree(s_src, s_dst)
            print(f"   ✓ Copied {item} to {s_dst.relative_to(SENTINEX_ROOT)}")
        else:
            print(f"   ✓ {item} already present in benchmark repository")

    # 3. Read metadata CSVs
    persons_csv_path = DATASET_PKG_DIR / "metadata" / "persons.csv"
    images_csv_path = DATASET_PKG_DIR / "metadata" / "images.csv"

    persons = []
    with open(persons_csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            persons.append(row)

    images = []
    with open(images_csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            images.append(row)

    print(f"\n📋 Loaded metadata: {len(persons)} identities, {len(images)} total images.")

    # 4. Enroll Cases (50 Missing + 50 Wanted)
    print("\n🏢 2. Enrolling Cases into Sentinex Database...")
    cases_enrolled = 0
    cases_map = {}  # person_id -> Case object

    for p in persons:
        cat_key = p["category"]
        person_id = p["person_id"]
        source_id = p.get("source_identity", person_id)

        if cat_key == "unknown_test":
            # Negative/un-enrolled probe set - intentionally not in gallery
            continue

        if cat_key == "missing_test":
            category = CaseCategory.MISSING.value
            dept_id = dept_missing.id
            title = f"Missing Person: {source_id} (Benchmark {person_id})"
            desc = (
                f"Controlled academic research benchmark missing person case {person_id}. "
                f"Source identity: {source_id} (LFW). Fictional prototype category."
            )
            priority = CasePriority.HIGH.value
        elif cat_key == "wanted_test":
            category = CaseCategory.WANTED.value
            dept_id = dept_central.id
            title = f"Wanted Person: {source_id} (Benchmark {person_id})"
            desc = (
                f"Controlled academic research benchmark wanted person case {person_id}. "
                f"Source identity: {source_id} (LFW). Fictional prototype category."
            )
            priority = CasePriority.HIGH.value
        else:
            continue

        case = db.query(Case).filter(Case.case_number == person_id).first()
        if not case:
            case = Case(
                case_number=person_id,
                category=category,
                title=title,
                person_identifier=f"PID-{person_id}",
                description=desc,
                department_id=dept_id,
                created_by=admin_user.id,
                status=CaseStatus.ACTIVE.value,
                priority=priority,
                last_known_location="Controlled Evaluation Sector",
                is_active=True,
            )
            db.add(case)
            db.flush()
            cases_enrolled += 1

        cases_map[person_id] = case

    db.commit()
    print(f"   ✓ Enrolled {cases_enrolled} new cases (Total active benchmark cases: {len(cases_map)})")

    # 5. Copy Reference Images and Enroll in reference_images table
    print("\n🖼️  3. Enrolling Reference Gallery Images...")
    ref_images = [img for img in images if img["split"] == "reference"]
    images_enrolled = 0
    ref_records = []

    for ref_img_info in ref_images:
        person_id = ref_img_info["person_id"]
        case = cases_map.get(person_id)
        if not case:
            continue

        cat_folder = "missing_persons" if case.category == CaseCategory.MISSING.value else "wanted_persons"
        case_img_dir = sentinex_datasets_root / cat_folder / person_id
        case_img_dir.mkdir(parents=True, exist_ok=True)

        rel_source_file = ref_img_info["file_name"]
        abs_src_file = DATASET_PKG_DIR / rel_source_file
        dest_filename = f"{ref_img_info['image_id']}.jpg"
        dest_file_path = case_img_dir / dest_filename

        # Copy image file to destination
        if not dest_file_path.exists():
            shutil.copy2(abs_src_file, dest_file_path)

        # Inspect dimensions
        with Image.open(dest_file_path) as im:
            width, height = im.size
        file_size = dest_file_path.stat().st_size

        # Check if already recorded in DB
        db_ref = (
            db.query(ReferenceImage)
            .filter(ReferenceImage.file_name == dest_filename)
            .first()
        )
        if not db_ref:
            # First reference image for this case is primary
            existing_for_case = (
                db.query(ReferenceImage)
                .filter(ReferenceImage.case_id == case.id)
                .count()
            )
            is_primary = (existing_for_case == 0)

            # Store path relative to workspace or absolute path
            stored_path = str(dest_file_path.resolve())

            db_ref = ReferenceImage(
                case_id=case.id,
                file_name=dest_filename,
                original_file_name=ref_img_info["source_file"],
                file_path=stored_path,
                storage_type="LOCAL",
                mime_type="image/jpeg",
                file_size=file_size,
                image_width=width,
                image_height=height,
                uploaded_by=admin_user.id,
                is_active=True,
                is_primary=is_primary,
                image_quality_status="VALID",
                processing_status="COMPLETED",
                description=f"Enrolled reference image for {person_id}",
                original_filename=ref_img_info["source_file"],
                stored_filename=dest_filename,
                file_type="image/jpeg",
                width=width,
                height=height,
                uploaded_at=datetime.utcnow(),
            )
            db.add(db_ref)
            db.flush()
            images_enrolled += 1

        ref_records.append((db_ref, case))

    db.commit()
    print(f"   ✓ Enrolled {images_enrolled} new reference images (Total in gallery: {len(ref_records)})")

    # 6. Extract and Store 512-dim Face Embeddings (Module 7)
    print("\n🧠 4. Computing Face Embeddings for Reference Gallery (Module 7)...")
    emb_service = FaceEmbeddingService()
    embeddings_created = 0

    gallery_embeddings = []  # List of tuples: (person_id, case_id, category, vector)

    for db_ref, case in ref_records:
        existing_emb = (
            db.query(FaceEmbeddingDB)
            .filter(FaceEmbeddingDB.reference_image_id == db_ref.id)
            .first()
        )

        if existing_emb:
            vec = np.frombuffer(existing_emb.vector_bytes, dtype=np.float32)
            gallery_embeddings.append((case.case_number, case.id, case.category, vec))
        else:
            vec = emb_service.extract_face_embedding(db_ref.file_path)
            if vec is None:
                print(f"   ⚠️ Could not extract embedding for {db_ref.file_path}")
                continue

            emb_ref_str = f"EMB-{db_ref.id}-{uuid4().hex[:8]}"
            new_emb = FaceEmbeddingDB(
                reference_image_id=db_ref.id,
                case_id=case.id,
                category=case.category,
                embedding_reference=emb_ref_str,
                model_name=emb_service.model_name,
                model_version=emb_service.model_version,
                embedding_dim=emb_service.embedding_dim,
                vector_bytes=vec.astype(np.float32).tobytes(),
                is_active=True,
            )
            db.add(new_emb)
            embeddings_created += 1
            gallery_embeddings.append((case.case_number, case.id, case.category, vec))

    db.commit()
    print(f"   ✓ Created {embeddings_created} new face embeddings (Total gallery embeddings: {len(gallery_embeddings)})")

    # 7. Model Registry & Dataset Registry (Module 11)
    print("\n📊 5. Updating Model & Dataset Registries...")
    # Register AnalyticalFaceEmbeddingModel if not in registry
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
        print(f"   ✓ Registered model '{emb_service.model_name}' in model_registry")
    else:
        print(f"   ✓ Model '{emb_service.model_name}' already registered")

    # Register Dataset in dataset_registry
    dataset_name = "Controlled 150-Person LFW Research Benchmark"
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
            source_type="LICENSED",
            sample_count=len(images),
            notes=(
                "Controlled 150-identity academic research evaluation dataset "
                "(50 missing_test, 50 wanted_test, 50 unknown_test) with reference and test probe splits."
            ),
            creation_date=datetime.utcnow(),
        )
        db.add(ds_reg)
        db.commit()
        db.refresh(ds_reg)
        print(f"   ✓ Registered dataset '{dataset_name}' in dataset_registry")
    else:
        print(f"   ✓ Dataset '{dataset_name}' already registered")

    # 8. Run Scientific Benchmark Evaluation (Module 11)
    print("\n🔬 6. Executing Scientific Evaluation Run on Test Probe Images...")
    test_images = [img for img in images if img["split"] == "test"]
    print(f"   Evaluating {len(test_images)} test probe images against {len(gallery_embeddings)} gallery entries...")

    gallery_matrix = np.array([e[3] for e in gallery_embeddings], dtype=np.float32)
    gallery_pids = [e[0] for e in gallery_embeddings]

    threshold = 0.70
    t0 = time.time()

    tp = 0
    fp = 0
    tn = 0
    fn = 0
    top1_correct = 0
    top5_correct = 0
    similarities = []
    latencies = []

    for img_info in test_images:
        p_t0 = time.time()
        probe_pid = img_info["person_id"]
        probe_cat = img_info["category"]
        probe_rel_file = img_info["file_name"]
        probe_path = DATASET_PKG_DIR / probe_rel_file

        probe_vec = emb_service.extract_face_embedding(str(probe_path))
        if probe_vec is None:
            continue

        # Cosine similarity against all gallery embeddings (both are L2 normalized -> dot product)
        sims = np.dot(gallery_matrix, probe_vec)
        max_idx = int(np.argmax(sims))
        best_sim = float(sims[max_idx])
        best_pid = gallery_pids[max_idx]

        latencies.append((time.time() - p_t0) * 1000.0)
        similarities.append(best_sim)

        top5_indices = np.argsort(sims)[-5:]
        top5_pids = [gallery_pids[i] for i in top5_indices]

        is_enrolled = (probe_cat in ["missing_test", "wanted_test"])

        if is_enrolled:
            if best_pid == probe_pid:
                top1_correct += 1
            if probe_pid in top5_pids:
                top5_correct += 1

            if best_sim >= threshold:
                if best_pid == probe_pid:
                    tp += 1
                else:
                    fp += 1
            else:
                fn += 1
        else:
            # Unknown test identity (not enrolled in gallery)
            if best_sim >= threshold:
                fp += 1
            else:
                tn += 1

    total_time = time.time() - t0
    enrolled_probe_count = sum(1 for img in test_images if img["category"] in ["missing_test", "wanted_test"])
    total_eval = tp + fp + tn + fn

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fmr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnmr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    top1_acc = top1_correct / enrolled_probe_count if enrolled_probe_count > 0 else 0.0
    top5_rate = top5_correct / enrolled_probe_count if enrolled_probe_count > 0 else 0.0
    avg_sim = float(np.mean(similarities)) if similarities else 0.0
    avg_lat = float(np.mean(latencies)) if latencies else 0.0

    print("\n   📊 Benchmark Results:")
    print(f"      • Operating Threshold: {threshold}")
    print(f"      • Evaluated Probes:    {total_eval} images in {total_time:.2f}s")
    print(f"      • Confusion Matrix:    TP={tp}, FP={fp}, TN={tn}, FN={fn}")
    print(f"      • Precision:           {precision:.4f} ({precision*100:.1f}%)")
    print(f"      • Recall:              {recall:.4f} ({recall*100:.1f}%)")
    print(f"      • F1-Score:            {f1:.4f}")
    print(f"      • False Match Rate:    {fmr:.4f}")
    print(f"      • False Non-Match:     {fnmr:.4f}")
    print(f"      • Top-1 Accuracy:      {top1_acc:.4f} ({top1_acc*100:.1f}%)")
    print(f"      • Top-5 Retrieval:     {top5_rate:.4f} ({top5_rate*100:.1f}%)")
    print(f"      • Avg Latency:         {avg_lat:.2f} ms")

    # Record Evaluation Run in DB
    run_id_str = f"EVAL-LFW150-{int(time.time())}"
    eval_run = EvaluationRunDB(
        run_id=run_id_str,
        run_name="150-Identity LFW Controlled Benchmark Evaluation",
        dataset_registry_id=ds_reg.id,
        model_registry_id=model_reg.id,
        model_name=emb_service.model_name,
        model_version=emb_service.model_version,
        dataset_name=ds_reg.dataset_name,
        dataset_version=ds_reg.dataset_version,
        threshold=threshold,
        status="COMPLETED",
        notes="Standard controlled evaluation protocol across 150 LFW identities (50 enrolled missing, 50 enrolled wanted, 50 unknown negative distractors).",
        justification="Strict operational point to assess precision and negative suppression.",
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
        true_negatives=tn,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        false_match_rate=round(fmr, 4),
        false_non_match_rate=round(fnmr, 4),
        top1_accuracy=round(top1_acc, 4),
        top5_retrieval_rate=round(top5_rate, 4),
        average_similarity_score=round(avg_sim, 4),
        average_latency_ms=round(avg_lat, 2),
        evaluated_at=datetime.utcnow(),
    )
    db.add(eval_result)
    db.commit()
    print(f"   ✓ Recorded evaluation run {run_id_str} in database")

    # 9. Sync database to backend/sentinex.db if backend/sentinex.db exists
    backend_db = SENTINEX_ROOT / "backend" / "sentinex.db"
    root_db = SENTINEX_ROOT / "sentinex.db"
    if backend_db.exists() and root_db.exists():
        shutil.copy2(root_db, backend_db)
        print(f"   ✓ Synchronized SQLite database to backend/sentinex.db")

    db.close()
    print("\n✅ Sentinex 150-Person Dataset Integration Completed Successfully!")
    print("=" * 70)


if __name__ == "__main__":
    run_integration()
