import pytest
import torch

from rnn_attention import RNNAttentionConfig, Seq2SeqRNNAttention

from transformers import AutoTokenizer, DataCollatorForSeq2Seq

import numpy as np
import evaluate
from transformers import  Seq2SeqTrainingArguments, Seq2SeqTrainer

import torch
import torch.nn as nn

from datasets import load_dataset

def test_rnn_attention_overfitting():

    books = load_dataset("opus_books", "en-fr")

    loaded_tokenizer = AutoTokenizer.from_pretrained("./rnn_tokenizer/")

    books["train"] = books["train"].select(range(10000))
    books = books.filter(lambda x: len(x['translation']['en']) < 250)

    source_lang = "en"
    target_lang = "fr"

    def preprocess_function(examples):
        inputs = [example[source_lang] for example in examples["translation"]]
        targets = [example[target_lang] for example in examples["translation"]]
        model_inputs = loaded_tokenizer(inputs, text_target=targets, max_length=64, truncation=True, add_special_tokens=True)
        return model_inputs

    books_preprocessed = books.map(preprocess_function, batched=True)

    metric = evaluate.load("sacrebleu")

    def postprocess_text(preds, labels):
        preds = [pred.strip() for pred in preds]
        labels = [[label.strip()] for label in labels]

        return preds, labels

    def compute_metrics(eval_preds):
        preds, labels = eval_preds
        if isinstance(preds, tuple):
            preds = preds[0]
        decoded_preds = loaded_tokenizer.batch_decode(preds, skip_special_tokens=True)

        labels = np.where(labels != -100, labels, loaded_tokenizer.pad_token_id)
        decoded_labels = loaded_tokenizer.batch_decode(labels, skip_special_tokens=True)

        decoded_preds, decoded_labels = postprocess_text(decoded_preds, decoded_labels)

        result = metric.compute(predictions=decoded_preds, references=decoded_labels)
        result = {"bleu": result["score"]}

        prediction_lens = [np.count_nonzero(pred != loaded_tokenizer.pad_token_id) for pred in preds]
        result["gen_len"] = np.mean(prediction_lens)
        result = {k: round(v, 4) for k, v in result.items()}
        return result


    test_rnn_config = RNNAttentionConfig(
        pad_token_id=loaded_tokenizer.pad_token_id,
        bos_token_id=loaded_tokenizer.bos_token_id,
        eos_token_id=loaded_tokenizer.eos_token_id,
    )


    rnn_attention_model_loaded = Seq2SeqRNNAttention(test_rnn_config)
    rnn_attention_model_loaded.load_state_dict( torch.load("./rnn_attention_model/pytorch_model.bin", map_location='cpu') )

    test_training_args = Seq2SeqTrainingArguments(
        output_dir="my_awesome_opus_books_model",
        evaluation_strategy="steps",
        eval_steps=500,
        learning_rate=1e-3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        weight_decay=0.01,
        save_total_limit=3,
        num_train_epochs=100,
        predict_with_generate=True,
        logging_steps=100,
    )


    data_collator = DataCollatorForSeq2Seq(tokenizer=loaded_tokenizer, return_tensors="pt")

    test_trainer = Seq2SeqTrainer(
        model=rnn_attention_model_loaded,
        args=test_training_args,
        eval_dataset=books_preprocessed["train"].select(torch.tensor(range(128))),  # валидировать будем тоже на обучающих данных (дисклаймер: это можно делать только для тестирования)
        tokenizer=loaded_tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    evaluate_result = test_trainer.evaluate(test_dataset=books_preprocessed["train"].select(range(128)))

    print("evaluate_result", evaluate_result)

    assert evaluate_result['eval_bleu'] >= 50




