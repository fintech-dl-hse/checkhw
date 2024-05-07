import pytest
import torch
import torch.nn

from vae import VariationalAutoEncoder

def seed_everything(seed: int):
    import random, os
    import numpy as np
    import torch

    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True

def test_smoke_variational_autoencoder():
    input_tensor = torch.rand( [ 5, 1, 28, 28 ] )
    variational_autoencoder_output = VariationalAutoEncoder().forward( input_tensor )
    assert len(variational_autoencoder_output) == 3, "VariationalAutoEncoder is expected to be a tuple of: reconstructed_image, images_embeddings_mean, images_embeddings_log_variance"
    assert input_tensor.shape == variational_autoencoder_output[0].shape, "Reconstructed image shape matches input image"

    return
