import torch
from torch import nn
import random
from my_autograd_mlp import Value, MLP


class TorchMLP(nn.Module):
    def __init__(self, n_in, hidden_dims):
        super().__init__()
        if len(hidden_dims) != 2:
            raise ValueError("hidden_dims должен содержать ровно два размера")
        h1, h2 = hidden_dims
        self.fc1 = nn.Linear(n_in, h1)
        self.fc2 = nn.Linear(h1, h2)
        self.fc3 = nn.Linear(h2, 1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        return self.fc3(x)


def _copy_micro_to_torch(micro_mlp, torch_mlp):
    micro_state = micro_mlp.state_dict()
    torch_layers = [torch_mlp.fc1, torch_mlp.fc2, torch_mlp.fc3]
    for layer_state, torch_layer in zip(micro_state, torch_layers):
        w = torch.tensor([n["w"] for n in layer_state], dtype=torch.float32)
        b = torch.tensor([n["b"] for n in layer_state], dtype=torch.float32)
        with torch.no_grad():
            torch_layer.weight.copy_(w)
            torch_layer.bias.copy_(b)


def test_torch_mlp_equivalence():
    # Тест сравнивает micrograd-реализацию и torch-репликацию по выходам и градиентам
    n_in = 3
    hidden_dims = [4, 5]
    n_trials = 5

    for _ in range(n_trials):
        micro_mlp = MLP(n_in, hidden_dims + [1])
        torch_mlp = TorchMLP(n_in, hidden_dims)
        _copy_micro_to_torch(micro_mlp, torch_mlp)

        x_values = [random.uniform(-1, 1) for _ in range(n_in)]
        x_micro = [Value(v) for v in x_values]
        x_torch = torch.tensor(x_values, dtype=torch.float32, requires_grad=True)

        micro_mlp.zero_grad()
        torch_mlp.zero_grad()

        y_micro = micro_mlp(x_micro)
        y_torch = torch_mlp(x_torch)

        y_micro.backward()
        y_torch.backward()

        assert abs(y_micro.data - y_torch.item()) < 1e-6

        torch_layers = [torch_mlp.fc1, torch_mlp.fc2, torch_mlp.fc3]
        for layer_idx, micro_layer in enumerate(micro_mlp.layers):
            torch_layer = torch_layers[layer_idx]
            for neuron_idx, micro_neuron in enumerate(micro_layer.neurons):
                for w_idx, w in enumerate(micro_neuron.w):
                    torch_grad = torch_layer.weight.grad[neuron_idx, w_idx].item()
                    assert abs(w.grad - torch_grad) < 1e-6
                b_grad = torch_layer.bias.grad[neuron_idx].item()
                assert abs(micro_neuron.b.grad - b_grad) < 1e-6


test_torch_mlp_equivalence()

print("OK")
