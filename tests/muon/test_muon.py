"""Tests for Muon optimizer."""
import copy

import pytest
import torch
import torch.nn as nn

from muon_optimizer import Muon


def test_muon_weights_stay_almost_orthogonal_after_10_steps():
    """
    After 10 steps with non-orthogonal gradients, weight matrix stays almost orthogonal
    when initialized orthogonally and step size is small enough.
    """
    torch.manual_seed(123)
    d = 32
    # Orthogonal init
    W = torch.randn(d, d)
    torch.nn.init.orthogonal_(W)
    W = nn.Parameter(W)
    opt = Muon([W], lr=0.01, beta=0.9, num_steps=3, kappa=2)
    # Non-orthogonal gradients (random) for 10 steps
    for _ in range(10):
        opt.zero_grad()
        W.grad = torch.randn(d, d) * 0.1
        opt.step()
    # Check orthogonality: singular values of W should be near 1
    S = torch.linalg.svdvals(W.detach())
    for s in S:
        assert s > 0.5 and s < 1.5, (
            f"weight matrix should stay almost orthogonal, got singular value {s.item()}"
        )
    # Also check W @ W.T close to scale * I (or W.T @ W)
    scale_sq = (W.detach() ** 2).sum() / d
    I = torch.eye(d, device=W.device, dtype=W.dtype)
    diff = (W.detach() @ W.detach().T - scale_sq * I).norm(p="fro").item()
    assert diff < 2.0 * (d ** 0.5), f"W W^T should be close to scaled I, fro diff = {diff}"


def test_muon_step_changes_weights():
    """One step of Muon changes 2D parameters."""
    torch.manual_seed(124)
    linear = nn.Linear(16, 8, bias=False)
    w_before = linear.weight.data.clone()
    opt = Muon(linear.parameters(), lr=0.05, beta=0.9, num_steps=2, kappa=2)
    linear( torch.randn(2, 16) ).sum().backward()
    opt.step()
    assert not torch.allclose(linear.weight.data, w_before), "weights should change after step"


def test_muon_skips_1d_params():
    """Muon only updates 2D params; 1D (e.g. bias) are unchanged by our convention or left as-is."""
    torch.manual_seed(125)
    model = nn.Linear(8, 4, bias=True)
    bias_before = model.bias.data.clone()
    opt = Muon(model.parameters(), lr=0.01, beta=0.9, num_steps=2, kappa=2)
    model(torch.randn(2, 8)).sum().backward()
    opt.step()
    # 2D weight should change
    assert model.weight.grad is not None
    # Bias: Muon skips 1D, so bias might be unchanged (no update) or unchanged by our impl
    # Our Muon only does param -= lr*O for ndim==2, so bias is not updated -> should be same
    assert torch.allclose(model.bias.data, bias_before), "bias (1D) should be unchanged by Muon"


@pytest.mark.skipif(
    not hasattr(torch.optim, "Muon"),
    reason="torch.optim.Muon requires PyTorch 2.10+",
)
def test_muon_close_to_torch_muon():
    """
    Result of optimization with student Muon should be close to torch.optim.Muon
    under the same setup (same init, same data, equivalent hyperparams).
    """
    torch.manual_seed(126)
    # Same model and data for both
    batch = 4
    steps = 25
    data = [torch.randn(batch, 16) for _ in range(steps)]
    targets = [torch.randint(0, 4, (batch,)) for _ in range(steps)]

    def run_muon(OptimizerClass, **kwargs):
        model = nn.Linear(16, 4, bias=False)
        torch.manual_seed(126)
        with torch.no_grad():
            nn.init.orthogonal_(model.weight)
        opt = OptimizerClass(model.parameters(), **kwargs)
        for x, y in zip(data, targets):
            opt.zero_grad()
            loss = nn.functional.cross_entropy(model(x), y)
            loss.backward()
            opt.step()
        return model.weight.data.clone()

    # Student Muon: lr, beta, num_steps, kappa
    w_student = run_muon(Muon, lr=0.02, beta=0.9, num_steps=2, kappa=2)

    # torch.optim.Muon: weight_decay=0, nesterov=False, same lr and momentum
    torch.manual_seed(126)
    w_torch = run_muon(
        torch.optim.Muon,
        lr=0.02,
        weight_decay=0.0,
        momentum=0.9,
        nesterov=False,
        ns_steps=2,
    )

    # Allow some tolerance (different NS details / scaling)
    assert torch.allclose(w_student, w_torch, atol=0.5, rtol=0.5), (
        "student Muon result should be close to torch.optim.Muon"
    )
