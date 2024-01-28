import pytest
import torch
import torch.nn as nn

def test_residual_block():

    from custom_resnet import ResBlock

    for layer_dim in (1, 4, 8):
        batch_size = 128

        image_size = (28, 28)
        batch = torch.rand([batch_size, layer_dim, *image_size])

        resblock = ResBlock(layer_dim, layer_dim * 2)

        batch_out = resblock(batch)

        assert batch_out.size() == batch.size(), f"layer_dim={layer_dim}: res block tensor dimension ok"


def test_resnet_forward():

    from custom_resnet import CustomResNet

    resnet = CustomResNet()

    batch_size = 128
    layers = 1
    image_size = (28, 28)
    batch = torch.rand([batch_size, layers, *image_size])

    batch_out = resnet.forward(batch)

    assert batch_out.size() == torch.Size([batch_size, 10]), "resnet forward dims are ok"
