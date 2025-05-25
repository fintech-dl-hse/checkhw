
import argparse

import datasets

from tqdm.auto import tqdm

# Импоритруем зависимости из файлика из ноутбука
from my_agent_tools import MyAgentTools
from my_agent_prompt import MyAgentPrompt

import logging

import datasets
from smolagents import ToolCallingAgent, OpenAIServerModel


logger = logging.getLogger(__name__)

# Важно!
# Код этой ячейки не стоит редактировать.
# В текущем виде код будет запускаться в автогрейдере.
# Изменения, которые вы сделаете у себя в ноутбуке не повлияют на
# код в автогрейдере. Но можете добавить сюда дебаг, если надо что-то отладить
#
# Если нашли ошибку, присылайте мердж реквест с исправлениями в fintech-dl-hse/checkhw
# https://github.com/fintech-dl-hse/checkhw/blob/main/tests/llm-agent/run_evaluation.py


MAX_AGENT_STEPS = 5


# Объект, через котроый мы будем ходить в API vllm
# Обратите внимание, что длинна контекста для этой модели 32k токенов!
model = OpenAIServerModel(
    model_id='Qwen/Qwen2.5-7B-Instruct-AWQ', # Будем использовать квантованую версию 7B модельки
    api_base='http://localhost:8000/v1',
    api_key='nokey',
)


def eval_agent(agent):
    eval_dataset = datasets.load_dataset("m-ric/huggingface_doc_qa_eval", split="train")
    eval_dataset = eval_dataset.filter(lambda x: x['source_doc'].startswith('huggingface/transformers') and '/en/' in x['source_doc'])

    print("eval_dataset len", len(eval_dataset))
    
    # Можете выбрать конкретные примеры, чтобы раздебажить только их
    # eval_dataset = eval_dataset.select([ 10, 11 ])

    outputs_agentic = []

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
        outputs_agentic.append(results_agentic)

    EVALUATION_PROMPT = """You are a fair evaluator language model.

    You will be given an instruction, a "response to evaluate", a "reference answer" that gets a score of 2, and a score rubric representing a evaluation criteria are given.
    1. Write a detailed feedback that assess the quality of the response strictly based on the given score rubric, not evaluating in general.
    2. After writing a feedback, write a score that is an integer between 1 and 2. You should refer to the score rubric.
    3. The output format should look as follows: \"Feedback: {{write a feedback for criteria}} [RESULT] {{an integer number between 1 and 2}}\"
    4. Please do not generate any other opening, closing, and explanations. Be sure to include [RESULT] in your output.
    5. Do not score conciseness: a correct answer that covers the question should receive max score, even if it contains additional useless information.

    The instruction to evaluate:
    {instruction}

    "reference answer" (Score 2):
    {reference_answer}

    "response to evaluate":
    {response}

    Score Rubrics:
    [Is the "response to evaluate" complete, accurate, and factual based on the "reference answer"?]
    Score 1: The response is incomplete, inaccurate. Or response says the answer could not be found in the available documentation
    Score 2: The response is complete and accurate.

    Feedback:"""

    # Вообще говоря, это не очень хорошо, что мы одну и ту же модель используем
    # для генерации и для LLM-as-a-judge оценки, потому что к своим генерациям
    # у LLM обычно есть смещение - и свои ответы часто оцениваются лучше, чем ответы других моделей.
    # Сейчас так сделано из-за ограниченности по ресурсам.
    evaluation_client = agent

    import pandas as pd

    results = {}
    for system_type, outputs in [
        ("agentic", outputs_agentic),
    ]:
        for experiment in tqdm(outputs):
            eval_prompt = EVALUATION_PROMPT.format(
                instruction=experiment["question"],
                response=experiment["generated_answer"],
                reference_answer=experiment["true_answer"],
            )

            print("\n\n========")
            print("question\t\t", experiment["question"])
            print("generated_answer", experiment["generated_answer"])
            print("true_answer\t", experiment["true_answer"])

            eval_result = evaluation_client.model.client.chat.completions.create(messages=[    {"role": "system", "content": "You are a fair evaluator language model."},    {"role": "user", "content": eval_prompt},], model=evaluation_client.model.model_id)
            eval_result = eval_result.choices[0].message.content
            try:
                feedback, score = [item.strip() for item in eval_result.split("[RESULT]")]
                print("score\t\t", score)
                experiment["eval_score_LLM_judge"] = score
                experiment["eval_feedback_LLM_judge"] = feedback
            except:
                print(f"Parsing failed - output was: {eval_result}")

        results[system_type] = pd.DataFrame.from_dict(outputs)
        results[system_type] = results[system_type].loc[~results[system_type]["generated_answer"].str.contains("Error")]

    DEFAULT_SCORE = 1 # Give average score whenever scoring fails
    def fill_score(x):
        try:
            return int(x)
        except:
            return DEFAULT_SCORE

    for system_type, outputs in [
        ("agentic", outputs_agentic),
    ]:

        results[system_type]["eval_score_LLM_judge_int"] = (
            results[system_type]["eval_score_LLM_judge"].fillna(DEFAULT_SCORE).apply(fill_score)
        )
        results[system_type]["eval_score_LLM_judge_int"] = (results[system_type]["eval_score_LLM_judge_int"] - 1) / 2

        print(
            f"Average score for {system_type}: {results['agentic']['eval_score_LLM_judge_int'].mean()*100:.2f}%"
        )

    return results['agentic']['eval_score_LLM_judge_int'].mean()*100


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=str, required=True)

    args = parser.parse_args()

    output_file_name = args.out

    knowledge_base = datasets.load_dataset("m-ric/huggingface_doc", split="train")
    knowledge_base = knowledge_base.filter(lambda x: x['source'].startswith('huggingface/transformers') and '/en/' in x['source'])

    agent_tools =  MyAgentTools.get(knowledge_base)
    agent_prompt_templates = MyAgentPrompt.get()

    print("agent_tools", agent_tools)

    agent = ToolCallingAgent(
        tools=agent_tools,
        model=model,
        prompt_templates=agent_prompt_templates,
        max_steps=10
    )

    qa_score = eval_agent(agent)

    with open(output_file_name, 'w') as f:
        f.write(f"{qa_score:.2f}\n")

