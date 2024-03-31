from tqdm.auto import tqdm
from torch.optim import SGD, Adam
import copy

import pytest
import torch
import torch.nn as nn

from myoptimizers import MySGD, MyAdam


# initialize a model
class MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.sequential = nn.Sequential(
            nn.Linear(784, 2048),
            nn.ReLU(),
            nn.Linear(2048, 100),
            nn.ReLU(),
            nn.Linear(100, 10)
        )
        return

    def forward(self, x_coordinates):
        # x_coordinates ~ [ batch_size, 2 ]
        scores = self.sequential(x_coordinates)   # [ batch_size, 10 ]
        return scores

def _optimizer_step(model, model_state, optimizer_class, optimizer_params, model_inputs_batches, target_labels_batches, criterion):
    model.load_state_dict(model_state)
    optimizer = optimizer_class(model.parameters(), **optimizer_params)

    for model_inputs, target_labels in zip(model_inputs_batches, target_labels_batches):
        model.zero_grad()

        prediction = model.forward(model_inputs)
        loss = criterion(prediction, target_labels)
        # print("loss", loss.item())
        loss.backward()
        optimizer.step()

        # print("list(model.parameters())", list(model.parameters()))

    return copy.deepcopy(list(model.parameters()))


def _test_my_optimizer(torch_optimizer, my_optimizer, optimizer_params,
                       model='linear',
                       batch_size = 3, num_batches = 10,
                       name=None,
                       ):

    if model == 'linear':
        model = nn.Linear(784, 10)
    else:
        model = MLP()

    model_state = copy.deepcopy(model.state_dict())

    criterion = nn.CrossEntropyLoss()

    model_inputs =  [torch.rand([batch_size, 784]) for _ in range(num_batches)]
    target_labels = [torch.randint(0, 10, [batch_size]) for _ in range(num_batches)]

    torch_updated_params = _optimizer_step(model, model_state, torch_optimizer, optimizer_params, model_inputs, target_labels, criterion)
    my_updated_params    = _optimizer_step(model, model_state, my_optimizer,    optimizer_params, model_inputs, target_labels, criterion)

    for torch_updated_param, my_updated_param in tqdm(zip(torch_updated_params, my_updated_params), total=len(torch_updated_params), desc=name):
        # print(torch_updated_param)
        # print(my_updated_param)
        assert torch.allclose(torch_updated_param, my_updated_param, rtol=0.5, atol=1e-3), 'updated parameters are not equal'

def test_my_sgd():
    optimizer_params = {
        "lr": 0.01
    }
    torch_optimizer = SGD
    my_optimizer = MySGD

    _test_my_optimizer(torch_optimizer, my_optimizer, optimizer_params, name="Test SGD Linear")
    _test_my_optimizer(torch_optimizer, my_optimizer, optimizer_params, model='mlp', name="Test SGD MLP")


def test_my_adam():
    optimizer_params = {
        "lr": 0.01
    }
    torch_optimizer = Adam
    my_optimizer = MyAdam

    _test_my_optimizer(torch_optimizer, my_optimizer, optimizer_params, name="Test Adam Linear")
    _test_my_optimizer(torch_optimizer, my_optimizer, optimizer_params, model='mlp', name="Test Adam MLP")


print("Tests are OK!")