import torch
import torch.nn as nn

from mylinear import MyLinear, task_linear_mse_loss, task_grad_sum_of_squares

def test_my_linear_basic():
    """Базовый тест для MyLinear: проверка формы выхода."""
    in_features = 5
    out_features = 3
    batch_size = 10

    layer = MyLinear(in_features, out_features)
    x = torch.randn(batch_size, in_features)

    # Проверка, что слой имеет правильные параметры
    assert hasattr(layer, 'weight'), "MyLinear должен иметь параметр weight"
    assert layer.weight.shape == (out_features, in_features), \
        f"weight должен иметь форму ({out_features}, {in_features}), получено {layer.weight.shape}"

    if layer.bias is not None:
        assert layer.bias.shape == (out_features,), \
            f"bias должен иметь форму ({out_features},), получено {layer.bias.shape}"

    # Проверка forward pass
    output = layer(x)
    assert output.shape == (batch_size, out_features), \
        f"Выход должен иметь форму ({batch_size}, {out_features}), получено {output.shape}"


def test_my_linear_no_bias():
    """Тест MyLinear без bias."""
    in_features = 4
    out_features = 2
    batch_size = 8

    layer = MyLinear(in_features, out_features, bias=False)
    x = torch.randn(batch_size, in_features)

    assert layer.bias is None, "При bias=False параметр bias должен быть None"

    output = layer(x)
    assert output.shape == (batch_size, out_features)


def test_my_linear_vs_torch_linear():
    """Сравнение MyLinear с nn.Linear (проверка правильности реализации)."""
    in_features = 7
    out_features = 4
    batch_size = 6

    # Создаем два слоя
    my_layer = MyLinear(in_features, out_features)
    torch_layer = nn.Linear(in_features, out_features)

    # Копируем веса из torch_layer в my_layer для сравнения
    my_layer.weight.data = torch_layer.weight.data.clone()
    if my_layer.bias is not None:
        my_layer.bias.data = torch_layer.bias.data.clone()

    x = torch.randn(batch_size, in_features)

    # Получаем выходы
    my_output = my_layer(x)
    torch_output = torch_layer(x)

    # Проверяем, что выходы совпадают (с небольшой погрешностью)
    assert torch.allclose(my_output, torch_output, atol=1e-5), \
        "Выход MyLinear должен совпадать с выходом nn.Linear при одинаковых весах"


def test_my_linear_gradients():
    """Проверка работы градиентов в MyLinear."""
    in_features = 3
    out_features = 2
    batch_size = 5

    layer = MyLinear(in_features, out_features)
    x = torch.randn(batch_size, in_features, requires_grad=True)

    output = layer(x)
    loss = output.sum()
    loss.backward()

    # Проверяем, что градиенты вычислены
    assert x.grad is not None, "Градиент по входу должен быть вычислен"
    assert layer.weight.grad is not None, "Градиент по weight должен быть вычислен"
    if layer.bias is not None:
        assert layer.bias.grad is not None, "Градиент по bias должен быть вычислен"


def test_task_linear_mse_loss():
    """Тест для task_linear_mse_loss."""
    in_features = 4
    out_features = 2
    batch_size = 5

    # Создаем слой и данные
    layer = MyLinear(in_features, out_features)
    x = torch.randn(batch_size, in_features)
    y = torch.randn(batch_size, out_features)

    # Вызываем функцию
    loss, weight_grad = task_linear_mse_loss(layer, x, y)

    # Проверки
    assert isinstance(loss, torch.Tensor), "loss должен быть torch.Tensor"
    assert loss.dim() == 0, "loss должен быть скаляром"

    assert isinstance(weight_grad, torch.Tensor), "weight_grad должен быть torch.Tensor"
    assert weight_grad.shape == (out_features, in_features), \
        f"weight_grad должен иметь форму ({out_features}, {in_features}), получено {weight_grad.shape}"

    # Проверяем, что градиент не None
    assert weight_grad is not None, "weight_grad не должен быть None"

    # Проверяем правильность вычисления loss вручную
    output = layer(x)
    expected_loss = ((output - y) ** 2).mean()
    assert torch.allclose(loss, expected_loss.detach(), atol=1e-5), \
        f"loss должен быть равен MSE: ожидалось {expected_loss.item()}, получено {loss.item()}"


def test_task_grad_sum_of_squares():
    x = torch.randn(4, 3, requires_grad=True)
    grad = task_grad_sum_of_squares(x)

    assert isinstance(grad, torch.Tensor), "Ожидается torch.Tensor"
    assert grad.shape == x.shape

    # d/dx sum(x^2) = 2x
    assert torch.allclose(grad, 2 * x.detach()), "Градиент должен быть равен 2*x"

