import torch
import torch.nn as nn

from clip_modeling import compute_clip_logits, clip_loss


def seed_everything(seed: int = 0):
    torch.manual_seed(seed)


# OpenAI CLIP initialises logit_scale to ln(1 / 0.07) ~= 2.6592
LOGIT_SCALE_INIT = 2.6592


def _reference_logits(image_embeds, text_embeds, logit_scale):
    img = image_embeds / image_embeds.norm(p=2, dim=-1, keepdim=True)
    txt = text_embeds / text_embeds.norm(p=2, dim=-1, keepdim=True)
    scale = logit_scale.exp()
    logits_per_text = txt @ img.t() * scale
    return logits_per_text.t(), logits_per_text


def test_logits_match_scaled_cosine_reference():
    """compute_clip_logits must L2-normalize AND scale by logit_scale.exp()."""
    seed_everything(0)
    image_embeds = torch.randn(8, 512)
    text_embeds = torch.randn(8, 512)
    logit_scale = nn.Parameter(torch.tensor(LOGIT_SCALE_INIT))

    logits_per_image, logits_per_text = compute_clip_logits(image_embeds, text_embeds, logit_scale)
    ref_image, ref_text = _reference_logits(image_embeds, text_embeds, logit_scale)

    assert logits_per_text.shape == (8, 8)
    assert logits_per_image.shape == (8, 8)
    assert torch.allclose(logits_per_text, ref_text, atol=1e-4), "logits_per_text mismatch"
    assert torch.allclose(logits_per_image, ref_text.t(), atol=1e-4), "logits_per_image must be logits_per_text.t()"


def test_embeddings_are_normalized_before_dot_product():
    """Without normalization the diagonal cosine of an embed with itself != 1."""
    seed_everything(1)
    embeds = torch.randn(6, 128)
    logit_scale = nn.Parameter(torch.tensor(0.0))  # exp(0) == 1 -> logits are pure cosine sim
    _, logits_per_text = compute_clip_logits(embeds, embeds, logit_scale)
    diag = torch.diagonal(logits_per_text)
    assert torch.allclose(diag, torch.ones_like(diag), atol=1e-4), \
        "diagonal cosine similarity of identical embeddings must be 1.0 (embeddings not normalized?)"


def test_logit_scale_actually_scales():
    """Changing logit_scale must change the logit magnitude (scaling is applied)."""
    seed_everything(2)
    image_embeds = torch.randn(4, 64)
    text_embeds = torch.randn(4, 64)
    _, logits_small = compute_clip_logits(image_embeds, text_embeds, nn.Parameter(torch.tensor(0.0)))
    _, logits_big = compute_clip_logits(image_embeds, text_embeds, nn.Parameter(torch.tensor(2.6592)))
    ratio = logits_big.abs().mean() / logits_small.abs().mean()
    assert ratio > 5.0, f"logit_scale does not seem to be applied (ratio={ratio:.2f}, expected ~exp(2.66)=14.3)"


def test_clip_loss_matches_huggingface_reference():
    """Symmetric clip_loss must match the transformers reference implementation."""
    seed_everything(3)
    logits_per_text = torch.randn(8, 8) * 3.0
    try:
        from transformers.models.clip.modeling_clip import clip_loss as hf_clip_loss
        reference = hf_clip_loss(logits_per_text)
    except Exception:
        # Fallback reference identical to HF implementation.
        def _cl(logits):
            return nn.functional.cross_entropy(logits, torch.arange(len(logits)))
        reference = (_cl(logits_per_text) + _cl(logits_per_text.t())) / 2.0
    student = clip_loss(logits_per_text)
    assert torch.allclose(student, reference, atol=1e-5), \
        f"clip_loss={student.item():.6f} != reference={reference.item():.6f}"


def test_perfectly_aligned_pairs_give_low_loss():
    """When matching pairs are aligned and scaled, the loss is near zero."""
    seed_everything(4)
    base = torch.randn(8, 256)
    logit_scale = nn.Parameter(torch.tensor(LOGIT_SCALE_INIT))
    _, logits_per_text = compute_clip_logits(base, base.clone(), logit_scale)
    loss = clip_loss(logits_per_text)
    assert loss.item() < 0.1, f"aligned pairs should give near-zero loss, got {loss.item():.4f}"


def test_gradient_flows_to_logit_scale():
    """logit_scale must receive a non-trivial gradient (it is a learnable parameter)."""
    seed_everything(5)
    image_embeds = torch.randn(8, 128, requires_grad=True)
    text_embeds = torch.randn(8, 128, requires_grad=True)
    logit_scale = nn.Parameter(torch.tensor(LOGIT_SCALE_INIT))

    _, logits_per_text = compute_clip_logits(image_embeds, text_embeds, logit_scale)
    loss = clip_loss(logits_per_text)
    loss.backward()

    assert logit_scale.grad is not None, "logit_scale got no gradient"
    assert logit_scale.grad.abs().item() > 0, "logit_scale gradient is zero (is logit_scale used?)"
