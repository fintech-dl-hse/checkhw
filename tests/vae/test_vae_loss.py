import pytest
import torch
import torch.nn

from vae_loss import vae_loss

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

def test_regularization_term():
    # В этом тесте проверяется корректность вычисления регуляризационной составляющей лосса
    seed_everything(42)

    test_target_image = torch.ones(10, 10)
    test_model_out = (test_target_image, torch.ones(10), torch.ones(10))

    expected_loss = torch.tensor(0.8591)
    calculated_loss = vae_loss(test_model_out, test_target_image, regularization_lambda=1.0)
    print("test_regularization_term: calculated_loss", calculated_loss)
    print("test_regularization_term: expected_loss", expected_loss)
    assert torch.allclose(calculated_loss, expected_loss, atol=1e-4), f"expected_loss={expected_loss} calculated_loss={calculated_loss}"

def test_reconstruct_term():
    # В этом тесте проверяется корректность вычисления составляющей лосса, отвечающей за реконструкцию
    seed_everything(42)

    test_target_image = torch.zeros(10, 10)
    test_model_out = (torch.ones(10, 10), torch.ones(10), torch.ones(10))

    expected_loss = torch.tensor(1.0)
    calculated_loss = vae_loss(test_model_out, test_target_image, regularization_lambda=0.0)
    print("test_reconstruct_term: calculated_loss", calculated_loss)
    print("test_reconstruct_term: expected_loss", expected_loss)
    assert torch.allclose(calculated_loss, expected_loss, atol=1e-4), f"expected_loss={expected_loss} calculated_loss={calculated_loss}"
