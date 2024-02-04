import pytest
import torch
import torch.nn as nn

from batchnorm2d import BatchNorm2dLayer

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

def _test_batch_norm(bn, torch_bn, description="train"):
    
    seed_everything(42)

    batch_size = 2
    image_size = (3, 3)

    for i in range(3):
        batch = torch.rand([ batch_size, torch_bn.num_features, *image_size ])
        batch_clone = batch.clone()

        my_bn_out    = bn.forward(batch)
        torch_bn_out = torch_bn.forward(batch)

        # print("my_bn_out", my_bn_out)
        # print("torch_bn_out", torch_bn_out)

        assert (batch_clone == batch).all(), "batch was not changed inside module"

        # check buffers
        assert torch_bn.num_batches_tracked == bn.num_batches_tracked, f"{description}: num_batches_tracked mismatch: {torch_bn.num_batches_tracked} == {bn.num_batches_tracked}"

        if torch_bn.track_running_stats:
            assert bn.running_mean.requires_grad == False, "bn.running_mean should not requires_grad. Use .detach() for per batch means"
            assert bn.running_var.requires_grad == False, "bn.running_var should not requires_grad. Use .detach() for per batch vars"

            assert torch_bn.running_mean.allclose(bn.running_mean), f"{description}: running_mean mismatch: {torch_bn.running_mean} == {bn.running_mean}"
            assert torch_bn.running_var.allclose(bn.running_var, rtol=0.1), f"{description}: running_var mismatch: {torch_bn.running_var} == {bn.running_var}"

        # check parameters
        if torch_bn.affine:
            assert torch_bn.weight.allclose(bn.weight), f"{description}: weight mismatch: {torch_bn.weight} == {bn.weight}"
            assert torch_bn.bias.allclose(bn.bias), f"{description}: bias mismatch: {torch_bn.bias} == {bn.bias}"

        assert torch_bn_out.allclose(my_bn_out, atol=1e-04, rtol=0.1), f"{description}: {i} torch normalized batch equals to yours one"

    return


def test_batch_norm_2d():

    seed_everything(42)

    with torch.no_grad():

        for num_channels in (1, 2, 3):

            test_descr = f"train: [channels={num_channels}]"

            bn = BatchNorm2dLayer(num_channels, track_running_stats=True).train()
            torch_bn = nn.BatchNorm2d(num_channels, track_running_stats=True).train()

            _test_batch_norm(bn, torch_bn, description=test_descr)

            bn.eval()
            torch_bn.eval()

            test_descr = f"eval: [channels={num_channels}]"
            _test_batch_norm(bn, torch_bn, description=test_descr)

def test_batch_norm_2d_do_not_track_running_stats():

    seed_everything(42)

    with torch.no_grad():

        for num_channels in (1, 2, 3):

            test_descr = f"train: [channels={num_channels}]"

            bn = BatchNorm2dLayer(num_channels, track_running_stats=False).train()
            torch_bn = nn.BatchNorm2d(num_channels, track_running_stats=False).train()

            _test_batch_norm(bn, torch_bn, description=test_descr)

            bn.eval()
            torch_bn.eval()

            test_descr = f"eval: [channels={num_channels}]"
            _test_batch_norm(bn, torch_bn, description=test_descr)

def test_batch_norm_2d_do_not_track_running_stats_not_affine():
    seed_everything(42)

    with torch.no_grad():

        for num_channels in (1, 2, 3):

            test_descr = f"train: [channels={num_channels}]"

            bn = BatchNorm2dLayer(num_channels, track_running_stats=False, affine=False).train()
            torch_bn = nn.BatchNorm2d(num_channels, track_running_stats=False, affine=False).train()

            _test_batch_norm(bn, torch_bn, description=test_descr)

            bn.eval()
            torch_bn.eval()

            test_descr = f"eval: [channels={num_channels}]"
            _test_batch_norm(bn, torch_bn, description=test_descr)


