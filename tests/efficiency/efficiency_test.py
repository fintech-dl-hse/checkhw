
from efficiency import prepare_model, prepare_dataloader, train_model
import os
from transformers import AutoTokenizer
import torch
from datasets import load_dataset

if __name__ == "__main__":
    os.environ['WANDB_DISABLED'] = 'true'

    # Load tokenizer and model
    model_name = "gpt2"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token

    dataset = load_dataset('HuggingFaceFW/fineweb', data_files=['data/CC-MAIN-2024-10/000_00000.parquet'])
    dataset['train'] = dataset['train'].select(range(6000))

    train_dataloader = prepare_dataloader(dataset, tokenizer)

    # Move model to device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = prepare_model(model_name)

    model = model.to(device)
    model.train()

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

    # Training loop
    num_epochs = 1
    moving_avg_loss = train_model(model, train_dataloader, optimizer, num_epochs)

    print(f"Moving average loss: {moving_avg_loss:.4f}")
    assert moving_avg_loss < 2.0
