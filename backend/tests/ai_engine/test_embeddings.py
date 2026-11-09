"""
Tests for Module 7 – Face Feature & Embedding Models
====================================================
Verifies embedding extraction, L2 normalization, determinism, batching,
empty/corrupted handling, and model versioning.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.ai_engine.matching.models.embedding_model import (
    AnalyticalFaceEmbeddingModel,
    BaseFaceEmbeddingModel,
    get_embedding_model,
)


def _create_test_face(base_val: int = 120, eye_val: int = 30) -> np.ndarray:
    """Creates a synthetic test face crop (112x112x3) with distinctive features."""
    img = np.full((112, 112, 3), base_val, dtype=np.uint8)
    # Eyes
    cv2.circle(img, (35, 40), 10, (eye_val, eye_val, eye_val), -1)
    cv2.circle(img, (75, 40), 10, (eye_val, eye_val, eye_val), -1)
    # Nose
    cv2.line(img, (56, 45), (56, 65), (50, 50, 50), 3)
    # Mouth
    cv2.ellipse(img, (56, 85), (20, 8), 0, 0, 180, (20, 20, 20), 2)
    return img


class TestAnalyticalEmbeddingModel:

    @pytest.fixture
    def model(self):
        return AnalyticalFaceEmbeddingModel(embedding_dim=512)

    def test_output_shape_and_dtype(self, model):
        img = _create_test_face()
        emb = model.extract_embedding(img)
        assert isinstance(emb, np.ndarray)
        assert emb.shape == (512,)
        assert emb.dtype == np.float32

    def test_vector_is_l2_normalized(self, model):
        img = _create_test_face()
        emb = model.extract_embedding(img)
        norm = float(np.linalg.norm(emb))
        assert pytest.approx(norm, abs=1e-5) == 1.0

    def test_extraction_is_deterministic(self, model):
        img = _create_test_face(base_val=130)
        emb1 = model.extract_embedding(img)
        emb2 = model.extract_embedding(img)
        assert np.allclose(emb1, emb2, atol=1e-6)

    def test_different_faces_produce_distinct_embeddings(self, model):
        face_a = _create_test_face(base_val=90, eye_val=10)
        face_b = _create_test_face(base_val=190, eye_val=80)

        emb_a = model.extract_embedding(face_a)
        emb_b = model.extract_embedding(face_b)

        # Cosine similarity between distinct faces should be less than 1.0
        cos_sim = float(np.dot(emb_a, emb_b))
        assert cos_sim < 0.95

    def test_batch_extraction(self, model):
        faces = [_create_test_face(base_val=80 + i * 20) for i in range(4)]
        batch_emb = model.extract_batch(faces)
        assert batch_emb.shape == (4, 512)
        for i in range(4):
            norm = float(np.linalg.norm(batch_emb[i]))
            assert pytest.approx(norm, abs=1e-5) == 1.0

    def test_empty_batch_handling(self, model):
        batch_emb = model.extract_batch([])
        assert batch_emb.shape == (0, 512)

    def test_empty_image_handling(self, model):
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        emb = model.extract_embedding(empty)
        assert emb.shape == (512,)
        assert pytest.approx(float(np.linalg.norm(emb)), abs=1e-5) == 1.0

    def test_none_image_handling(self, model):
        emb = model.extract_embedding(None)
        assert emb.shape == (512,)
        assert pytest.approx(float(np.linalg.norm(emb)), abs=1e-5) == 1.0

    def test_model_metadata_provenance(self, model):
        assert model.model_name == "ANALYTICAL_V1"
        assert model.model_version == "1.0.0"
        assert model.embedding_dim == 512

    def test_l2_normalize_zero_vector(self):
        zero_v = np.zeros(512, dtype=np.float32)
        norm_v = BaseFaceEmbeddingModel.l2_normalize(zero_v)
        assert norm_v.shape == (512,)
        assert pytest.approx(float(np.linalg.norm(norm_v)), abs=1e-5) == 1.0


class TestModelFactory:

    def test_factory_returns_analytical_model(self):
        m = get_embedding_model("ANALYTICAL_V1")
        assert isinstance(m, AnalyticalFaceEmbeddingModel)
        assert m.embedding_dim == 512

    def test_factory_fallback_on_unknown(self):
        m = get_embedding_model("NON_EXISTENT_MODEL_XYZ")
        assert isinstance(m, AnalyticalFaceEmbeddingModel)
