import pytest
import torch
import torch.nn as nn


def test_cnn_forward():

    from custom_cnn import CustomCNN

    cnn = CustomCNN()

    batch_size = 128
    layers = 1
    image_size = (28, 28)
    batch = torch.rand([batch_size, layers, *image_size])

    batch_out = cnn.forward(batch)

    assert batch_out.size() == torch.Size([batch_size, 10]), "cnn forward dims are ok"
