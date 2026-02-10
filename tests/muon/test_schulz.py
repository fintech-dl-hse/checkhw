"""Tests for Newton–Schulz orthogonalization (schulz_orthogonalize)."""
import math

import pytest
import torch

from schulz_orthogonalize import schulz_orthogonalize


def test_schulz_signature_and_shape():
    """Return value has same shape and device as input."""
    for m, n in [(32, 32), (64, 32), (16, 64)]:
        X = torch.randn(m, n) * 0.5
        Y = schulz_orthogonalize(X, num_steps=3, kappa=2)
        assert Y.shape == X.shape, f"shape mismatch: {Y.shape} vs {X.shape}"
        assert Y.device == X.device
        assert Y.dtype == X.dtype


def test_schulz_orthogonality_square():
    """For square matrix with norm <= 1, Y @ Y.T ≈ I."""
    torch.manual_seed(42)
    X = torch.randn(32, 32) * 0.5
    Y = schulz_orthogonalize(X, num_steps=5, kappa=2)
    I = torch.eye(32, device=Y.device, dtype=Y.dtype)
    diff = (Y @ Y.T - I).norm(p="fro").item()
    assert diff < 2.0, f"Y @ Y.T should be close to I, fro norm diff = {diff}"


def test_schulz_orthogonality_tall():
    """For tall matrix (m > n), Y.T @ Y ≈ I (min(m,n) x min(m,n))."""
    torch.manual_seed(43)
    X = torch.randn(48, 24) * 0.5
    Y = schulz_orthogonalize(X, num_steps=5, kappa=2)
    I = torch.eye(24, device=Y.device, dtype=Y.dtype)
    diff = (Y.T @ Y - I).norm(p="fro").item()
    assert diff < 1.0, f"Y.T @ Y should be close to I, fro norm diff = {diff}"


def test_schulz_orthogonality_wide():
    """For wide matrix (n > m), Y @ Y.T ≈ I."""
    torch.manual_seed(44)
    X = torch.randn(24, 48) * 0.5
    Y = schulz_orthogonalize(X, num_steps=5, kappa=2)
    I = torch.eye(24, device=Y.device, dtype=Y.dtype)
    diff = (Y @ Y.T - I).norm(p="fro").item()
    assert diff < 1.0, f"Y @ Y.T should be close to I, fro norm diff = {diff}"


def test_schulz_singular_values_polar_like():
    """Singular values of result should be in a reasonable range (polar approximation)."""
    torch.manual_seed(45)
    X = torch.randn(20, 20) * 0.4
    Y = schulz_orthogonalize(X, num_steps=6, kappa=2)
    S = torch.linalg.svdvals(Y)
    # Should be in [0, 1.5] and at least one significant (polar-like)
    assert S.max() > 0.3, "result should have non-trivial singular values"
    for s in S:
        assert 0 <= s.item() <= 2.0, f"singular value {s.item()} out of range"
