
import torch

from transformer_block import TransformerBlock

@torch.no_grad()
def test_transformer_block():

    # Arrange
    bs = 3
    hidden_dim = 16
    spatial_pixels = 4
    transformer_block = TransformerBlock(spatial_pixels=spatial_pixels, hidden_dim=hidden_dim, condition_dim=16)

    # Transformer Block State
    test_transformer_block_data = torch.load("test_transformer_block.pt")

    # Inputs
    x = test_transformer_block_data['x']
    timesteps_embeds = test_transformer_block_data['timesteps_embeds']
    condition_embeddings = test_transformer_block_data['condition_embeddings']

    # Expected Output
    transformer_block_state = test_transformer_block_data['transformer_block_state']
    transformer_block.load_state_dict(transformer_block_state)

    expected_out = test_transformer_block_data['expected_out']

    # Act
    out = transformer_block.forward(x, timesteps_embeds, condition_embeddings=condition_embeddings)

    assert torch.allclose(out, expected_out, atol=1e-4)
