
import argparse
import pandas as pd

from torch.utils.data import DataLoader
import torch
import torch.nn as nn

from transformers.generation import GenerationConfig

import evaluate
import datasets

from tqdm.auto import tqdm

# Импоритруем зависимости из файлика из ноутбука
from my_agent_tools import MyAgentTools
from my_agent_prompt import MyAgentPrompt

import logging

import datasets
import copy


logger = logging.getLogger(__name__)


def eval_agent(agent):
    eval_dataset = datasets.load_dataset("m-ric/huggingface_doc_qa_eval", split="train")
    eval_dataset = eval_dataset.filter(lambda x: x['source_doc'].startswith('huggingface/transformers') and '/en/' in x['source_doc'])

    first_question_copy = copy.deepcopy(eval_dataset[0])
    first_question_copy['question'] = 'Каков размер контекстного окна по умолчанию для локального внимания в модели Long T5?'

    eval_dataset = datasets.concatenate_datasets([ eval_dataset, datasets.Dataset.from_list( [ first_question_copy ] )  ])
    print("eval_dataset len", len(eval_dataset))

    # Можете выбрать конкретные примеры, чтобы раздебажить только их
    # eval_dataset = eval_dataset.select([ 10, 11 ])

    outputs_agentic_rag = []

    for example in tqdm(eval_dataset):
        question = example["question"]

        enhanced_question = f"""Question: {question}"""
        answer = agent.run(enhanced_question)
        print("=======================================================")
        print(f"Question: {question}")
        print(f"Answer: {answer}")
        print(f'True answer: {example["answer"]}')

        results_agentic = {
            "question": question,
            "true_answer": example["answer"],
            "source_doc": example["source_doc"],
            "generated_answer": answer,
        }
        outputs_agentic_rag.append(results_agentic)


    """The evaluation prompt follows some of the best principles shown in [our llm_judge cookbook](llm_judge): it follows a small integer Likert scale, has clear criteria, and a description for each score."""

    EVALUATION_PROMPT = """You are a fair evaluator language model.

    You will be given an instruction, a response to evaluate, a reference answer that gets a score of 3, and a score rubric representing a evaluation criteria are given.
    1. Write a detailed feedback that assess the quality of the response strictly based on the given score rubric, not evaluating in general.
    2. After writing a feedback, write a score that is an integer between 1 and 3. You should refer to the score rubric.
    3. The output format should look as follows: \"Feedback: {{write a feedback for criteria}} [RESULT] {{an integer number between 1 and 3}}\"
    4. Please do not generate any other opening, closing, and explanations. Be sure to include [RESULT] in your output.
    5. Do not score conciseness: a correct answer that covers the question should receive max score, even if it contains additional useless information.

    The instruction to evaluate:
    {instruction}

    Response to evaluate:
    {response}

    Reference Answer (Score 3):
    {reference_answer}

    Score Rubrics:
    [Is the response complete, accurate, and factual based on the reference answer?]
    Score 1: The response is completely incomplete, inaccurate, and/or not factual, or response says that it is not able to answer the question or documentation does not contain the answer.
    Score 2: The response is somewhat complete, accurate, and/or factual.
    Score 3: The response is completely complete, accurate, and/or factual. Its ok if the response contains additional information that is not in the reference answer.

    Feedback:"""

    # Вообще говоря, это не очень хорошо, что мы одну и ту же модель используем
    # для генерации и для LLM-as-a-judge оценки, потому что к своим генерациям
    # у LLM обычно есть смещение - и свои ответы часто оцениваются лучше, чем ответы других моделей.
    # Сейчас так сделано из-за ограниченности по ресурсам.
    evaluation_client = agent

    import pandas as pd

    results = {}
    for system_type, outputs in [
        ("agentic", outputs_agentic_rag),
    ]:
        for experiment in tqdm(outputs):
            eval_prompt = EVALUATION_PROMPT.format(
                instruction=experiment["question"],
                response=experiment["generated_answer"],
                reference_answer=experiment["true_answer"],
            )

            eval_result = evaluation_client.model.client.chat.completions.create(messages=[    {"role": "system", "content": "You are a fair evaluator language model."},    {"role": "user", "content": eval_prompt},], model=evaluation_client.model.model_id)
            eval_result = eval_result.choices[0].message.content
            try:
                feedback, score = [item.strip() for item in eval_result.split("[RESULT]")]
                experiment["eval_score_LLM_judge"] = score
                experiment["eval_feedback_LLM_judge"] = feedback
            except:
                print(f"Parsing failed - output was: {eval_result}")

        results[system_type] = pd.DataFrame.from_dict(outputs)
        results[system_type] = results[system_type].loc[~results[system_type]["generated_answer"].str.contains("Error")]

    DEFAULT_SCORE = 2 # Give average score whenever scoring fails
    def fill_score(x):
        try:
            return int(x)
        except:
            return DEFAULT_SCORE

    for system_type, outputs in [
        ("agentic", outputs_agentic_rag),
    ]:

        results[system_type]["eval_score_LLM_judge_int"] = (
            results[system_type]["eval_score_LLM_judge"].fillna(DEFAULT_SCORE).apply(fill_score)
        )
        results[system_type]["eval_score_LLM_judge_int"] = (results[system_type]["eval_score_LLM_judge_int"] - 1) / 2

        print(
            f"Average score for {system_type} RAG: {results['agentic']['eval_score_LLM_judge_int'].mean()*100:.2f}%"
        )

    return results['agentic']['eval_score_LLM_judge_int'].mean()*100


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=str, required=True)

    args = parser.parse_args()

    output_file_name = args.out

    agent =

    qa_score = eval_agent(agent)

    with open(output_file_name, 'w') as f:
        f.write(f"{qa_score:.2f}\n")

