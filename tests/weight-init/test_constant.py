import pytest
import torch

def test_zeros():
    model_state = torch.load('All Zeros.pt')

    for k, v in model_state.items():
        if k.startswith("fc") and k.endswith(".weight"):
            assert (v == 0).all().item(), f"{k} has all zeros"

def test_ones():
    model_state = torch.load('All Ones.pt')

    for k, v in model_state.items():
        if k.startswith("fc") and k.endswith(".weight"):
            assert (v == 1).all().item(), f"{k} has all zeros"