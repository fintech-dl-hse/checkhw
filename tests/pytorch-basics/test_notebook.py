from sklearn.metrics import accuracy_score
import pandas as pd

import os
import subprocess

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from nbconvert.preprocessors import CellExecutionError

import wandb

def test_notebook():
    """
    Проверяем, что ноутбук запускается, отрабатывает без ошибок
    """

    wandb.disabled = True

    with open('./hw_pytorch_basics.ipynb') as f:
        nb = nbformat.read(f, as_version=4)

    ep = ExecutePreprocessor(timeout=1800, kernel_name='python3', allow_errors=False)

    try:
        # Check that the notebook runs
        ep.preprocess(nb, {'metadata': {'path': ''}})
    except CellExecutionError:
        raise

    print("Notebook successfully executed`")

