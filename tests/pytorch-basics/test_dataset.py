import pytest

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

import torch.optim as optim
from torchvision import transforms
from torchvision.datasets import MNIST

import matplotlib.pyplot as plt

transform_to_tensor = transforms.Compose([
    transforms.ToTensor()
])

def _test_dataset(dataset, test_name=""):

    assert len(dataset) > 0, f"{test_name}: dataset length is greater then zero"

    idateset = iter(dataset)
    item = next(idateset)

    assert isinstance(item, dict), f"{test_name}: dataset returned dict"
    assert "image" in item, f"{test_name}: dataset item dict has image"
    assert "label" in item, f"{test_name}: dataset item dict has label"

    assert item['image'].shape == (1, 28, 28), f"{test_name}: dataset image shape is correct. Got: {item['image'].shape}"

def test_dataset_mnist():
    from dataset_mnist import DatasetMNIST

    mydataset = DatasetMNIST(train=False, transform=transform_to_tensor)
    _test_dataset(mydataset, test_name="val")

    mydataset = DatasetMNIST(train=True, transform=transform_to_tensor)
    _test_dataset(mydataset, test_name="train")
