
import argparse

from torch.utils.data import DataLoader
import torch
import torch.nn as nn

from transformers.generation import GenerationConfig

import evaluate
import datasets

import pathlib
import random

from tqdm.auto import tqdm

# Импоритруем зависимости из файлика из ноутбука
from llaaa import Llaaa, llama_lm

import logging

logger = logging.getLogger(__name__)


class TrainConfig:
    log_level = "DEBUG"
    # Training
    num_epochs = 5
    train_batch_size = 8
    val_batch_size = 8
    log_grad_norm = True
    learning_rate = 1e-4
    gradient_accumulation_steps = 1

    evaluate_every_epoch_mod = 4
    save_model_every_epoch_mod = 1

    # Model
    llaaa_from_pretrained = None
    modality_tokens = 32
    llm_train_lora = False
    llm_lora_from_pretrained = None

    # Data
    few_train_samples = None
    few_val_samples = 100
    dataloader_num_workers = 0

    train_dataset_path = "data/CLOTHO_v2.1/clotho_hf_dataset/clotho_development_imagebind_single.dataset/"
    audio_embeds_train_prefix = "data/CLOTHO_v2.1/clotho_audio_embeds_processed_imagebind_single/development/"

    val_dataset_path = "data/CLOTHO_v2.1/clotho_hf_dataset/clotho_validation_imagebind_single.dataset/"
    audio_embeds_val_prefix = "data/CLOTHO_v2.1/clotho_audio_embeds_processed_imagebind_single/validation/"

class DummyAudioEncoder(nn.Module):

    hidden_size = 1024

    def encode_audio(self, audio_melspec_values):
        return torch.zeros([audio_melspec_values.shape[0], 1, self.hidden_size], device=audio_melspec_values.device)


def data_preloader(audio_embeds_path_prefix):

    def _data_preloader(items):
        result = {
            "audio_embeds_last_hidden_state": [],
        }

        for k in items.keys():
            k: str
            if k.startswith('caption_'):
                result[k] = items[k]

        for audio_embeds_path in items["audio_embeds_last_hidden_state_file_name"]:
            audio_embeds_full_path = pathlib.Path(audio_embeds_path_prefix).joinpath(audio_embeds_path)
            audio_embeds = torch.load(audio_embeds_full_path, map_location='cpu')
            result["audio_embeds_last_hidden_state"].append(audio_embeds)

        return result

    return _data_preloader


def get_collate_fn(tokenizer, validation=False):
    def collate_fn(items):
        result = dict()
        # random select caption
        current_caption_i = random.randint(1, 5)
        tokenizer_input = [item[f'caption_{current_caption_i}'] for item in items]
        tokenized_caption = tokenizer(tokenizer_input, padding=True)
        result['input_ids'] = torch.tensor(tokenized_caption['input_ids'])
        result['attention_mask'] = torch.tensor(tokenized_caption['attention_mask'])
        # result['pixel_values'] = torch.cat([x['pixel_values'] for x in items], dim=0)
        result['audio_embeds_last_hidden_state'] = torch.cat([x['audio_embeds_last_hidden_state'] for x in items], dim=0)

        if validation:
            all_captions = []
            for item in items:
                for current_caption_i in range(1, 6):
                    all_captions.append(item[f'caption_{current_caption_i}'])

            tokenized_caption = tokenizer(all_captions, padding=True)
            result['all_input_ids'] = torch.tensor(tokenized_caption['input_ids'])
            result['all_attention_mask'] = torch.tensor(tokenized_caption['attention_mask'])
        return result
    return collate_fn

def get_val_dataloader(
        train_config: TrainConfig, llaaa: Llaaa, tokenizer,
        val_dataset_path,
        audio_embeds_val_prefix):

    audio_captions_dataset_val: datasets.Dataset = datasets.load_from_disk(val_dataset_path)
    if train_config.few_val_samples is not None:
        audio_captions_dataset_val = audio_captions_dataset_val.select(range(train_config.few_val_samples))

    audio_captions_dataset_val.set_transform(data_preloader(audio_embeds_val_prefix))

    return DataLoader(audio_captions_dataset_val,
                      collate_fn=get_collate_fn(tokenizer, validation=True),
                      batch_size=train_config.val_batch_size)

def get_audio_embeds_last_hidden_state(model, batch):
    if 'audio_embeds_last_hidden_state' in batch:
        audio_embeds_last_hidden_state = batch['audio_embeds_last_hidden_state'].to(model.device)
    else:
        audio_melspec_values = batch['pixel_values'].to(model.device)
        audio_embeds_last_hidden_state = model.encode_audio(audio_melspec_values)
    return audio_embeds_last_hidden_state


@torch.no_grad()
def compute_validation_metrics(generations, target_generations, captioning_metrics=None):
    validation_metrics = {}
    if captioning_metrics is not None:
        evaluate_bleu_results = captioning_metrics.compute(predictions=generations, references=target_generations)
        logger.info(f"evaluate_bleu_results {evaluate_bleu_results}")

        validation_metrics["validation/evaluate_bleu"] = evaluate_bleu_results['bleu'] * 100
        validation_metrics["validation/evaluate_rouge1"] = evaluate_bleu_results['rouge1']
        validation_metrics["validation/evaluate_rouge2"] = evaluate_bleu_results['rouge2']
        validation_metrics["validation/evaluate_rougeL"] = evaluate_bleu_results['rougeL']
        validation_metrics["validation/evaluate_rougeLsum"] = evaluate_bleu_results['rougeLsum']
        validation_metrics["validation/evaluate_meteor"] = evaluate_bleu_results['meteor']

    return validation_metrics


def prepare_model_inputs_from_batch(model: Llaaa, batch):
    if 'audio_embeds_last_hidden_state' in batch:
        audio_embeds_last_hidden_state = batch['audio_embeds_last_hidden_state'].to(model.device)
    else:
        audio_melspec_values = batch['pixel_values'].to(model.device)
        audio_embeds_last_hidden_state = model.encode_audio(audio_melspec_values)

    inputs_embeds = model.encode_text(batch['input_ids'].to(model.device))

    model_inputs_with_audio = model.prepare_audio_inputs(
        inputs_embeds=inputs_embeds,
        attention_mask=batch['attention_mask'].to(model.device),
        audio_embeds=audio_embeds_last_hidden_state,
    )

    return {
        "inputs_embeds":  model_inputs_with_audio["inputs_embeds"],
        "attention_mask": model_inputs_with_audio["attention_mask"],
    }

@torch.no_grad()
def val_loop(model: Llaaa, tokenizer, val_dataloader: DataLoader, epoch, no_loss=False, captioning_metrics=None):

    criterion = nn.CrossEntropyLoss(ignore_index=tokenizer.pad_token_id)

    logger.info(f"go validation {epoch}")
    sumloss = 0
    num_batches = 0

    generations = []
    target_generations = []

    gen_params = {
        "do_sample": False,
        "early_stopping": True,
        "num_beams": 3,
        "repetition_penalty": 2.5,
        "remove_invalid_values": True,
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.eos_token_id,
        "forced_eos_token_id": tokenizer.eos_token_id,
        "use_cache": True,
        "no_repeat_ngram_size": 4,
        "num_return_sequences": 1,
    }
    genconfig = GenerationConfig.from_model_config(model.lm_model.config)

    model.eval()
    for batch in tqdm(val_dataloader):

        batch_input_ids = batch['input_ids'].to(model.device)
        caption_legth = batch_input_ids.shape[1]

        if not no_loss:
            model_inputs_with_audio = prepare_model_inputs_from_batch(model, batch)

            model_prediction = model(**model_inputs_with_audio)

            model_prediction_caption = model_prediction.logits[:, -caption_legth:-1, :]  # [ bs, caption_length - 1, vocad_size ]
            shifted_batch_input_ids = batch_input_ids[:, 1:]  # [ bs, caption_length - 1 ]

            model_prediction_caption_flatten = model_prediction_caption.flatten(0, 1)
            input_ids_flatten = shifted_batch_input_ids.flatten(0, 1)
            loss = criterion(model_prediction_caption_flatten, input_ids_flatten)

            sumloss += loss.item()
            num_batches += 1

        audio_embeds_last_hidden_state = get_audio_embeds_last_hidden_state(model, batch)

        model_inputs_with_only_audio = model.prepare_audio_inputs(
            audio_embeds=audio_embeds_last_hidden_state,
        )

        genconfig.max_length = caption_legth

        all_generation_params = {
            'generation_config': genconfig,
            'max_new_tokens': caption_legth,
            **model_inputs_with_only_audio,
            **gen_params,
        }

        model_generation = model.lm_model.generate(**all_generation_params)
        generated_sentences = tokenizer.batch_decode(model_generation, skip_special_tokens=True)
        for sentence in generated_sentences:
            sentence: str
            sentence = sentence.replace("\n", " ")
            generations.append(sentence)

        one_audio_references = []
        all_references = tokenizer.batch_decode(batch['all_input_ids'], skip_special_tokens=True)
        assert len(all_references) % 5 == 0, f'len(all_references) {len(all_references)}'
        for i, reference in enumerate(all_references):
            reference: str
            reference = reference.replace("\n", " ")
            one_audio_references.append(reference)
            if (i+1) % 5 == 0:
                target_generations.append(one_audio_references)
                one_audio_references = []

    assert len(generations) > 0, f"len(generations)={len(generations)}"
    assert len(target_generations) == len(generations), f"len(target_generations) == len(generations): {len(target_generations)} == {len(generations)}"

    validation_metrics = compute_validation_metrics(generations, target_generations, captioning_metrics=captioning_metrics)
    validation_metrics["validation/loss"] = sumloss / (num_batches + 1e-5)

    return validation_metrics


def data_preloader(audio_embeds_path_prefix):

    def _data_preloader(items):
        result = {
            "audio_embeds_last_hidden_state": [],
        }

        for k in items.keys():
            k: str
            if k.startswith('caption_'):
                result[k] = items[k]

        for audio_embeds_path in items["audio_embeds_last_hidden_state_file_name"]:
            audio_embeds_full_path = pathlib.Path(audio_embeds_path_prefix).joinpath(audio_embeds_path)
            audio_embeds = torch.load(audio_embeds_full_path, map_location='cpu')
            result["audio_embeds_last_hidden_state"].append(audio_embeds)

        return result

    return _data_preloader


def get_collate_fn(tokenizer, validation=False):
    def collate_fn(items):
        result = dict()
        # random select caption
        current_caption_i = random.randint(1, 5)
        tokenizer_input = [item[f'caption_{current_caption_i}'] for item in items]
        tokenized_caption = tokenizer(tokenizer_input, padding=True)
        result['input_ids'] = torch.tensor(tokenized_caption['input_ids'])
        result['attention_mask'] = torch.tensor(tokenized_caption['attention_mask'])
        # result['pixel_values'] = torch.cat([x['pixel_values'] for x in items], dim=0)
        result['audio_embeds_last_hidden_state'] = torch.cat([x['audio_embeds_last_hidden_state'] for x in items], dim=0)

        if validation:
            all_captions = []
            for item in items:
                for current_caption_i in range(1, 6):
                    all_captions.append(item[f'caption_{current_caption_i}'])

            tokenized_caption = tokenizer(all_captions, padding=True)
            result['all_input_ids'] = torch.tensor(tokenized_caption['input_ids'])
            result['all_attention_mask'] = torch.tensor(tokenized_caption['attention_mask'])
        return result
    return collate_fn

def get_val_dataloader(
        train_config: TrainConfig, llaaa: Llaaa, tokenizer,
        val_dataset_path,
        audio_embeds_val_prefix):

    audio_captions_dataset_val: datasets.Dataset = datasets.load_from_disk(val_dataset_path)
    if train_config.few_val_samples is not None:
        audio_captions_dataset_val = audio_captions_dataset_val.select(range(train_config.few_val_samples))

    audio_captions_dataset_val.set_transform(data_preloader(audio_embeds_val_prefix))

    return DataLoader(audio_captions_dataset_val,
                      collate_fn=get_collate_fn(tokenizer, validation=True),
                      batch_size=train_config.val_batch_size)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=str, required=True)

    args = parser.parse_args()

    output_file_name = args.out

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print("device", device)

    train_config = TrainConfig()

    audio_encoder = DummyAudioEncoder()
    lm_model, tokenizer = llama_lm()
    lm_model.to(device)
    audio_encoder.to(device)

    model = Llaaa.from_pretrained(lm_model, audio_encoder, './llaaa_pretrained/')
    model.to(device)

    train_config.few_val_samples = None
    train_config.val_batch_size = 8
    full_val_dataloader = get_val_dataloader(
        train_config, model, tokenizer,
        val_dataset_path=train_config.val_dataset_path,
        audio_embeds_val_prefix=train_config.audio_embeds_val_prefix,
    )

    captioning_metrics = evaluate.combine(
        [
            evaluate.load("bleu", keep_in_memory=True),
            evaluate.load("rouge", keep_in_memory=True),
            evaluate.load("meteor", keep_in_memory=True),
        ]
    )

    validation_metrics = val_loop(model, tokenizer, full_val_dataloader, epoch=-1, captioning_metrics=captioning_metrics)
    validation_bleu = validation_metrics['validation/evaluate_bleu']

    print("validation_bleu", validation_bleu, "out", output_file_name)

    with open(output_file_name, 'w') as f:
        f.write(f"{validation_bleu:.2f}\n")

