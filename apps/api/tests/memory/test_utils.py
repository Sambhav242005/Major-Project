"""Utility tests — _cosine_similarity."""

import pytest


def test_cosine_similarity_identical():
    """_cosine_similarity returns 1.0 for identical vectors."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert result == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    """_cosine_similarity returns 0.0 for orthogonal vectors."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([1.0, 0.0], [0.0, 1.0])
    assert result == pytest.approx(0.0)


def test_cosine_similarity_opposite():
    """_cosine_similarity returns -1.0 for opposite vectors."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([1.0, 0.0], [-1.0, 0.0])
    assert result == pytest.approx(-1.0)


def test_cosine_similarity_different_lengths():
    """_cosine_similarity returns 0.0 for different length vectors."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])
    assert result == 0.0


def test_cosine_similarity_zero_vector():
    """_cosine_similarity returns 0.0 when either vector is zero."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([0.0, 0.0], [1.0, 0.0])
    assert result == 0.0
