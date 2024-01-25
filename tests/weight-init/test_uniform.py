import pytest
import torch
from scipy import stats
import numpy as np

def test_uniform_baseline():
    model_state = torch.load('Uniform Weights.pt')

    for k, v in model_state.items():

        if k.startswith("fc") and k.endswith(".weight"):
            _, pvalue = stats.kstest(v.numpy().reshape(-1), stats.uniform(loc=0.0, scale=1.0).cdf)
            assert pvalue > 0.01, f"{k} maybe has uniform [0, 1] distribution, pvalue={pvalue}"

def test_uniform_centered():
    model_state = torch.load('Centered Weights [-0.5, 0.5).pt')

    for k, v in model_state.items():

        if k.startswith("fc") and k.endswith(".weight"):
            _, pvalue = stats.kstest(v.numpy().reshape(-1), stats.uniform(loc=-0.5, scale=1.0).cdf)
            assert pvalue > 0.01, f"{k} maybe has uniform [-0.5, 0.5) distribution, pvalue={pvalue}"


def test_uniform_general():
    model_state = torch.load('General Rule [-y, y).pt')

    for k, v in model_state.items():

        if k.startswith("fc") and k.endswith(".weight"):
            y = 1 / np.sqrt(v.shape[1])
            _, pvalue = stats.kstest(v.numpy().reshape(-1), stats.uniform(loc=-y, scale=2*y).cdf)
            assert pvalue > 0.01, f"{k} maybe has uniform [-y, y] distribution, pvalue={pvalue}"

