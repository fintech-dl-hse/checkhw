"""Lightweight, CPU-only, deterministic 'does it actually learn?' check.

We build a tiny synthetic multimodal dataset: each sample i has an image feature
and a text feature that both derive from a shared latent concept vector z_i (plus
noise). A correct contrastive setup -- L2-normalized embeddings, cosine similarity
SCALED by logit_scale.exp(), symmetric cross-entropy -- lets two small linear
projections align matching image/text pairs, so in-batch retrieval becomes perfect.

If the scaling (logit_scale) is missing, the cosine logits live in [-1, 1], the
softmax is almost uniform, gradients vanish, and retrieval stays near chance.
This is exactly the bug students debug to discover that they need logit_scale.
"""
import torch
import torch.nn as nn

from clip_modeling import compute_clip_logits, clip_loss

LOGIT_SCALE_INIT = 2.6592


def _make_synthetic_dataset(n=32, latent_dim=16, img_feat=48, txt_feat=40, noise=0.05, seed=0):
    g = torch.Generator().manual_seed(seed)
    z = torch.randn(n, latent_dim, generator=g)            # shared concept per pair
    A = torch.randn(latent_dim, img_feat, generator=g)     # fixed "image encoder"
    B = torch.randn(latent_dim, txt_feat, generator=g)     # fixed "text encoder"
    image_feats = z @ A + noise * torch.randn(n, img_feat, generator=g)
    text_feats = z @ B + noise * torch.randn(n, txt_feat, generator=g)
    return image_feats, text_feats


class _TinyCLIP(nn.Module):
    def __init__(self, img_feat, txt_feat, proj_dim=16):
        super().__init__()
        self.img_proj = nn.Linear(img_feat, proj_dim, bias=False)
        self.txt_proj = nn.Linear(txt_feat, proj_dim, bias=False)
        self.logit_scale = nn.Parameter(torch.tensor(LOGIT_SCALE_INIT))

    def forward(self, image_feats, text_feats):
        image_embeds = self.img_proj(image_feats)
        text_embeds = self.txt_proj(text_feats)
        return compute_clip_logits(image_embeds, text_embeds, self.logit_scale)


def _train_and_eval(steps=400, lr=0.05, seed=0):
    torch.manual_seed(seed)
    image_feats, text_feats = _make_synthetic_dataset(seed=seed)
    model = _TinyCLIP(image_feats.shape[1], text_feats.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=lr)

    first_loss = None
    for _ in range(steps):
        opt.zero_grad()
        _, logits_per_text = model(image_feats, text_feats)
        loss = clip_loss(logits_per_text)
        loss.backward()
        opt.step()
        # keep logit_scale in the CLIP range (<= ln(100)), like HF does
        with torch.no_grad():
            model.logit_scale.clamp_(max=4.6052)
        if first_loss is None:
            first_loss = loss.item()

    with torch.no_grad():
        logits_per_image, _ = model(image_feats, text_feats)
        n = logits_per_image.shape[0]
        targets = torch.arange(n)
        img_to_txt = (logits_per_image.argmax(dim=1) == targets).float().mean().item()
        txt_to_img = (logits_per_image.argmax(dim=0) == targets).float().mean().item()
    return first_loss, loss.item(), img_to_txt, txt_to_img


def test_contrastive_training_converges():
    first_loss, last_loss, img_to_txt, txt_to_img = _train_and_eval()
    assert last_loss < first_loss, f"loss did not decrease ({first_loss:.3f} -> {last_loss:.3f})"
    assert img_to_txt >= 0.9, f"image->text retrieval accuracy too low: {img_to_txt:.2f}"
    assert txt_to_img >= 0.9, f"text->image retrieval accuracy too low: {txt_to_img:.2f}"
    # The decisive check -- it separates the EXP scaling from the two near-misses:
    #   * no scaling (scale=1): cosines stay in [-1, 1], softmax can't peak, loss
    #     floors at ~2.5.
    #   * scaling by the RAW logit_scale (no .exp()): logit_scale is learnable and
    #     clamped to 4.6052, so the scale tops out at ~4.6 and the loss only stalls
    #     around ~0.3 -- still "decreasing", retrieval still perfect, so the looser
    #     thresholds above DON'T catch it.
    # Only exp() lets the scale grow to exp(4.6052)=100, collapsing the loss toward
    # zero (~0.0). The < 0.05 floor is what actually pins down logit_scale.exp() --
    # the exact "non-obvious detail" of this assignment.
    assert last_loss < 0.05, (
        f"final loss {last_loss:.3f} did not collapse toward zero. "
        "The cosine similarities must be scaled by logit_scale.exp(), not by the "
        "raw logit_scale (which stalls the loss around ~0.3) and not unscaled."
    )


def test_training_is_deterministic():
    a = _train_and_eval(seed=0)
    b = _train_and_eval(seed=0)
    assert abs(a[1] - b[1]) < 1e-6, "training must be deterministic for the same seed"
