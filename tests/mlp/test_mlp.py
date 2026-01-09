import torch
from mymlp import MyMLP
import torch.nn as nn

def count_learnable_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

def test_count_parameters():
    # Если вы все сделали правильно, должны пройти ассерты
    # Новый интерфейс: hidden_dims задаёт все скрытые размерности.

    model_1_hidden_layer = MyMLP(hidden_dims=[100, 100])
    assert count_learnable_parameters(model_1_hidden_layer) == 10501
    assert model_1_hidden_layer.forward(torch.rand(10, 2)).shape == torch.Size([10, 1])

    model_2_hidden_layer = MyMLP(hidden_dims=[100, 100, 100])
    assert count_learnable_parameters(model_2_hidden_layer) == 20601

    model_3_hidden_layer = MyMLP(hidden_dims=[100, 100, 100, 100])
    assert count_learnable_parameters(model_3_hidden_layer) == 30701


def _assert_linear_shapes(layer: nn.Linear, in_dim: int, out_dim: int):
    assert isinstance(layer, nn.Linear), f"Expected nn.Linear, got {type(layer)}"
    assert layer.in_features == in_dim, f"in_features: expected {in_dim}, got {layer.in_features}"
    assert layer.out_features == out_dim, f"out_features: expected {out_dim}, got {layer.out_features}"


def test_hidden_layers_order_and_shapes():
    input_dim = 2
    output_dim = 3

    # Case 1: single hidden layer => hidden_layers must be empty
    hidden_dims = [5]
    model = MyMLP(input_dim=input_dim, output_dim=output_dim, hidden_dims=hidden_dims, activation_cls=nn.ReLU)

    _assert_linear_shapes(model.input_layer, input_dim, hidden_dims[0])
    assert isinstance(model.hidden_layers, nn.ModuleList), "hidden_layers must be nn.ModuleList"
    assert len(model.hidden_layers) == 0, f"Expected 0 hidden layers, got {len(model.hidden_layers)}"
    _assert_linear_shapes(model.output_layer, hidden_dims[-1], output_dim)

    # Case 2: multiple hidden layers => ModuleList must connect hidden_dims sequentially
    hidden_dims = [4, 7, 11]
    model = MyMLP(input_dim=input_dim, output_dim=output_dim, hidden_dims=hidden_dims, activation_cls=nn.ReLU)

    _assert_linear_shapes(model.input_layer, input_dim, hidden_dims[0])

    assert isinstance(model.hidden_layers, nn.ModuleList), "hidden_layers must be nn.ModuleList"
    assert len(model.hidden_layers) == len(hidden_dims) - 1, (
        f"Expected {len(hidden_dims) - 1} hidden layers, got {len(model.hidden_layers)}"
    )

    expected_pairs = list(zip(hidden_dims[:-1], hidden_dims[1:]))  # (in_dim, out_dim) per hidden layer
    for i, (layer, (in_dim, out_dim)) in enumerate(zip(model.hidden_layers, expected_pairs)):
        assert isinstance(layer, nn.Linear), f"hidden_layers[{i}] must be nn.Linear, got {type(layer)}"
        _assert_linear_shapes(layer, in_dim, out_dim)

    _assert_linear_shapes(model.output_layer, hidden_dims[-1], output_dim)
