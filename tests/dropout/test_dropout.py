import pytest
import torch
import torch.nn

from dropout import DropoutLayer

def seed_everything(seed: int):
    import random, os
    import numpy as np
    import torch
    
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True

def test_dropout_train():
    
    seed_everything(42)

    zero_proba = 0.9
    do = DropoutLayer(p=zero_proba, inplace=False)

    assert do.p == zero_proba, f"zero_proba is ok"

    do.train()

    input_tensor = torch.rand( (7, 3, 28, 28) )
    input_tensor_clone = input_tensor.clone()

    dropouted_tensor = do(input_tensor)

    assert (input_tensor_clone == input_tensor).all(), "input tensor was not changed"

    zeroed_values = (dropouted_tensor == 0).sum()
    # print("input_tensor.numel()", input_tensor.numel())
    expected_zeroed_values = input_tensor.numel() * do.p

    assert (zeroed_values - expected_zeroed_values).abs() < 200, f"zeroed_values={zeroed_values} expected_zeroed_values={expected_zeroed_values}"

    input_module = input_tensor.abs().sum()
    output_module = dropouted_tensor.abs().sum()
    module_diff = (input_module - output_module).abs()
    assert module_diff < 1000, f"input_norm {input_module}, outout_norm {output_module}, diff={module_diff}"

def test_dropout_eval():

    seed_everything(42)

    with torch.no_grad():

        zero_proba = 0.9
        do = DropoutLayer(p=zero_proba, inplace=False)

        assert do.p == zero_proba, f"zero_proba is ok"

        do.eval()

        input_tensor = torch.rand( (7, 3, 28, 28) )
        input_tensor_clone = input_tensor.clone()

        dropouted_tensor = do(input_tensor)

        assert (input_tensor_clone == input_tensor).all(), "input tensor was not changed"
        assert (dropouted_tensor == input_tensor_clone).all(), "output tensor equals to input"

