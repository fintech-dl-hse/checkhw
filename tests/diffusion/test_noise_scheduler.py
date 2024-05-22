
import torch

from .noise_scheduler import NoiseScheduler
from .transformer_block import TransformerBlock


@torch.no_grad()
def test_noise_scheduler_add_noise():
    ns = NoiseScheduler()

    test_noise_scheduler_add_noise_data = torch.load("test_noise_scheduler_add_noise.pt")
    x_start = test_noise_scheduler_add_noise_data['x_start']
    x_noise = test_noise_scheduler_add_noise_data['x_noise']

    expected_noisy_sample = test_noise_scheduler_add_noise_data['noisy_sample']

    timesteps = torch.arange(len(ns))

    noisy_sample = ns.add_noise(x_start, x_noise, timesteps)

    assert torch.allclose(noisy_sample, expected_noisy_sample, atol=1e-4)

@torch.no_grad()
def test_noise_scheduler_step():
    ns = NoiseScheduler()

    batch_size = 7
    num_channels = 3
    spatial_size = 28

    test_noise_scheduler_step_data = torch.load("test_noise_scheduler_step.pt") 

    sample = test_noise_scheduler_step_data['sample']
    model_output = test_noise_scheduler_step_data['model_output']
    unconditional_model_output = test_noise_scheduler_step_data['unconditional_model_output']
    classifier_free_guidance_scale = test_noise_scheduler_step_data['classifier_free_guidance_scale']

    noise = test_noise_scheduler_step_data['noise']

    # Обратите внимание, в этом тесте не настоящий семплинг --
    # Для того чтобы минимизировать возможную накопленную ошибку вычислений
    for timestep in range(len(ns)):
        noisy_sample = ns.step(model_output, timestep, sample, unconditional_model_output=unconditional_model_output, classifier_free_guidance_scale=classifier_free_guidance_scale, noise=noise)

        test_data_key = f"noisy_sample_{timestep}"
        expected_noisy_sample = test_noise_scheduler_step_data[test_data_key]
        assert torch.allclose(expected_noisy_sample, noisy_sample, atol=1e-3)

    return
