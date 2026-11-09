#!/usr/bin/env python3
'''Evaluate pretrained OpenCV SFace on Sentinex's held-out 150-person split.'''
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import cv2
import numpy as np
ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "datasets/benchmarks/face_dataset_150"
DETECTOR = ROOT / "backend/face_detection_yunet_2023mar.onnx"
RECOGNIZER = ROOT / "backend/face_recognition_sface_2021dec.onnx"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thresholds", default="0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70")
    parser.add_argument(
        "--gallery", choices=("single", "mean"), default="single",
        help="Use individual reference vectors or one normalized per-identity mean prototype.",
    )
    args = parser.parse_args()

    detector = cv2.FaceDetectorYN.create(str(DETECTOR), "", (250, 250), 0.5, 0.3, 20)
    recognizer = cv2.FaceRecognizerSF.create(str(RECOGNIZER), "")
    with (DATASET / "metadata/images.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    embeddings: dict[str, tuple[dict[str, str], np.ndarray]] = {}
    misses = 0
    for row in rows:
        image = cv2.imread(str(DATASET / row["file_name"]))
        if image is None:
            misses += 1
            continue
        height, width = image.shape[:2]
        detector.setInputSize((width, height))
        count, faces = detector.detect(image)
        if faces is None or count == 0:
            misses += 1
            continue
        face = max(faces, key=lambda result: result[14])
        aligned = recognizer.alignCrop(image, face)
        vector = recognizer.feature(aligned).flatten().astype(np.float32)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            misses += 1
            continue
        embeddings[row["image_id"]] = (row, vector / norm)

    references = [(row, vector) for row, vector in embeddings.values() if row["split"] == "reference"]
    probes = [(row, vector) for row, vector in embeddings.values() if row["split"] == "test"]
    if args.gallery == "mean":
        # Average all independently enrolled reference views, then renormalize.
        # This reduces pose/lighting noise and prevents identities with more
        # references from receiving extra chances by max pooling.
        identity_vectors: dict[str, list[np.ndarray]] = {}
        for row, vector in references:
            identity_vectors.setdefault(row["person_id"], []).append(vector)
        gallery_ids = list(identity_vectors)
        gallery = np.stack([
            (mean := np.mean(vectors, axis=0)) / np.linalg.norm(mean)
            for vectors in identity_vectors.values()
        ]).astype(np.float32)
    else:
        gallery = np.stack([vector for _, vector in references])
        gallery_ids = [row["person_id"] for row, _ in references]
    scored: list[tuple[str, float, bool]] = []
    top1_hits = 0
    enrolled_count = 0
    for row, vector in probes:
        similarities = gallery @ vector
        best = int(np.argmax(similarities))
        correct_identity = gallery_ids[best] == row["person_id"]
        scored.append((row["category"], float(similarities[best]), correct_identity))
        if row["category"] != "unknown_test":
            enrolled_count += 1
            top1_hits += int(correct_identity)

    unknown_scores = [score for category, score, _ in scored if category == "unknown_test"]
    print(f"Images embedded: {len(embeddings)}/{len(rows)}; detector/decoder misses: {misses}")
    print(f"Gallery mode: {args.gallery}; gallery vectors: {len(gallery_ids)} ({len(references)} source references); held-out probes: {len(probes)}")
    print(f"Enrolled top-1 identification: {top1_hits}/{enrolled_count} ({top1_hits / max(1, enrolled_count):.4f})")
    if unknown_scores:
        print(f"Unknown best-score min/mean/max: {min(unknown_scores):.4f}/{np.mean(unknown_scores):.4f}/{max(unknown_scores):.4f}")

    for threshold in (float(value) for value in args.thresholds.split(",")):
        tp = sum(category != "unknown_test" and score >= threshold and correct for category, score, correct in scored)
        fp = sum(score >= threshold and (category == "unknown_test" or not correct) for category, score, correct in scored)
        fn = sum(category != "unknown_test" and (score < threshold or not correct) for category, score, correct in scored)
        tn = sum(category == "unknown_test" and score < threshold for category, score, _ in scored)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        fmr = fp / (fp + tn) if fp + tn else 0.0
        print(f"threshold={threshold:.2f} TP={tp} FP={fp} FN={fn} TN={tn} precision={precision:.4f} recall={recall:.4f} FMR={fmr:.4f}")

if __name__ == "__main__":
    main()
