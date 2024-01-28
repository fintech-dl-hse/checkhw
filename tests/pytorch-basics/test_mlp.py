import pytest
import torch
import torch.nn as nn


def test_cnn_forward():

    from custom_mlp import CustomMLP

    mlp = CustomMLP()

    batch_size = 128
    image_size = (784,)
    batch = torch.rand([batch_size, *image_size])

    batch_out = mlp.forward(batch)

    assert batch_out.size() == torch.Size([batch_size, 10]), "mlp forward dims are ok"
