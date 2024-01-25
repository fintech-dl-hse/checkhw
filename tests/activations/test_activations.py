import pytest
import torch
import torch.nn as nn

def _check_pytorch_module_was_not_used(file, module):

    file = open(file, mode='r')
    
    assert module not in file.read(), "pytorch module must not be used in you activation implementation"
    
    file.close()

    return

def _test_activation(myactivation, torch_activation):
    print(myactivation)

    with torch.no_grad():

        randinput = torch.rand([100])
        myactivation_output = myactivation(randinput)

        assert id(myactivation_output) != id(randinput), 'pytorch activation function must return new tensor'

        for _ in range(100):
            randinput = torch.rand([5, 5, 5])

            assert torch.allclose(myactivation(randinput), torch_activation(randinput)), 'activation output is not equals to touch ones output'

def test_relu():
    from myrelu import MyReLU

    my_activation = MyReLU()
    
    _check_pytorch_module_was_not_used("myrelu.py", '.ReLU(')
    _test_activation(my_activation, nn.ReLU())

def test_leaky_relu():
    from myleakyrelu import MyLeakyReLU

    my_activation = MyLeakyReLU()
    
    _check_pytorch_module_was_not_used("myleakyrelu.py", '.LeakyReLU(')
    _test_activation(my_activation, nn.LeakyReLU())

def test_sigmoid():
    from mysigmoid import MySigmoid

    my_activation = MySigmoid()
    
    _check_pytorch_module_was_not_used("mysigmoid.py", '.MySigmoid(')
    _test_activation(my_activation, nn.Sigmoid())

def test_elu():
    from myelu import MyELU

    my_activation = MyELU()
    
    _check_pytorch_module_was_not_used("myelu.py", '.MyELU(')
    _test_activation(my_activation, nn.ELU())

