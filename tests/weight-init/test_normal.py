import pytest
import torch

import numpy as np
from scipy import stats

def test_normal():
    model_state = torch.load('Normal Distribution.pt')

    for k, v in model_state.items():

        if k.startswith("fc") and k.endswith(".weight"):
            y = 1 / np.sqrt(v.shape[1])

            v_flat = v.numpy().reshape(-1)
            assert np.isclose(v_flat.mean(), 0, atol=y, rtol=y), f"normal distribution mean = 0: {v_flat.mean()}"
            assert np.isclose(v_flat.std(), y, atol=y, rtol=y), f"normal distribution std = {y}: {v_flat.std()}"
