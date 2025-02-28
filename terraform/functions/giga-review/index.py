import re
import os
import sys
import json

import requests

from gigachat import GigaChat

assert os.environ['GIGACHAT_CREDENTIALS'] is not None


def paper_link_to_file_name(paper_link):
    papers_prefix = "data/papers/"
    os.makedirs(papers_prefix, exist_ok=True)

    filename = os.path.join(papers_prefix, paper_link.split('/')[-1])
    if not filename.endswith('.pdf'):
        filename = filename + '.pdf'

    return filename


def upload_to_gigachat_cloud(model, paper_bytes):

    if len(paper_bytes) > 30000000:
        print("too large file size:", len(paper_bytes), "limit is 30MB")
        return None

    gc_file = model.upload_file(paper_bytes)
    return gc_file.id_

    # with open(paper_file_name, "rb") as f:

    #     mapping_filename = paper_file_name + '.mapping'

    #     if os.path.exists(mapping_filename):
    #         print("mapping file already exists:", mapping_filename)
    #         return mapping_filename


    #     with open(mapping_filename, "w", encoding='UTF-8') as mapping_file:
    #         mapping_file.write(str(gc_file.id_))
    #         print("mapping saved", gc_file.id_)

    # return mapping_filename


def download_paper_pdf(paper_link):
    response = requests.get(paper_link, timeout=10)

    if response.status_code == 200:
        return response.content

    print("Failed to download file", paper_link)
    breakpoint()
    return None


def parse_model_outputs(model_generated_content: str):

    # [ { title: "**1. Authors**", content: "Blablalba" } ]
    parsed_content = []

    current_title = None
    current_content = ''
    for line in model_generated_content.split("\n"):
        if line.startswith("**"):
            # Cut of the number

            if current_title is not None:
                # save the prev title
                parsed_content.append({
                    "title": current_title,
                    "content": current_content,
                })
                current_content = ''

            current_title = line
        else:
            current_content += line + '\n'

    # the last one
    parsed_content.append({
        "title": current_title,
        "content": current_content,
    })

    return parsed_content


def giga_review(model, prompt, paper_link):

    if '/abs/' in paper_link:
        paper_link = paper_link.replace('/abs/', '/pdf/')

    content = download_paper_pdf(paper_link)
    if content is None:
        return None, "Failed to download paper"

    file_id = upload_to_gigachat_cloud(model, content)

    result = model.chat(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "attachments": [file_id],
                }
            ],
            "temperature": 0.0
        }
    )
    total_tokens = result.usage.total_tokens
    model_output_content = result.choices[0].message.content

#     total_tokens = 0
#     model_output_content = """**Title**: Yet Another RoPE Extension Method (YaRN)
# **Authors**: Bowen Peng, Jeffrey Quesnelle, Honglu Fan, Enrico Shippole
# **Affiliations**: Nous Research, EleutherAI, University of Geneva
# **Problem**: Extend the context window of large language models (LLMs) trained with Rotary Position Embeddings (RoPE) to handle longer sequences than their original pre-training allowed.
# **Results**: The YaRN method significantly extends the context window of LLMs with RoPE, reducing computational requirements by 10x and training steps by 2.5x compared to prior methods. Fine-tuning required only 0.1% of the original pre-training data. The method surpasses state-of-the-art context window extension approaches.
# **Methods**: YaRN employs a novel approach to interpolate RoPE embeddings, focusing on preserving high-frequency information and local distances. It includes dynamic scaling for efficient inference and achieves substantial performance without extensive fine-tuning.
# **Model Architecture**: The architecture remains largely unchanged except for modifications to positional embeddings. Specific architectural details and parameter counts are not provided.
# **Strengths**: Efficiency (requires less data and training time), effectiveness (surpasses state-of-the-art), and applicability (broad compatibility with libraries like Flash Attention 2).
# **Weaknesses**: Specific to models trained with RoPE, potential sensitivity to hyperparameter tuning for optimal results.
# **Computational Resources**: Details on GPU usage and hours are not explicitly stated in the provided excerpt."""

    print(model_output_content)

    print("\nresult total tokens:", total_tokens, "\n\n")

    return model_output_content, None


class TelegramBot():
    def __init__(self):

        self._telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', None)
        if self._telegram_bot_token is None:
            raise ValueError("TELEGRAM_BOT_TOKEN env var is required")

    def send_message(self, chat_id, message, **kwargs):
        resp = requests.post(
            f"https://api.telegram.org/bot{self._telegram_bot_token}/sendMessage",
            json={
                'text': message,
                'parse_mode': 'MarkdownV2',
                'link_preview_options': {'is_disabled': True},
                'chat_id': chat_id,
                **kwargs
            },
            timeout=10,
        )

        return resp


def handler(event, context):

    if event['secret_token'] != os.environ['TELEGRAM_BOT_WEBHOOK_SECRET_TOKEN']:
        print("invalid secret token")
        return {
            'statusCode': 200,
            'body': '',
        }

    try:
        event_body = json.loads(event['body'])
    except Exception as e:
        print("invalid body, can't parse json", e)
        return {
            'statusCode': 200,
            'body': '',
        }

    print("event_body", event_body)

    model = GigaChat(
        model="GigaChat-Pro",
        scope="GIGACHAT_API_PERS",
        verify_ssl_certs=False,
        timeout=300,
    )

    SYSTEM_PROMPT_EN = """
Give a brief review of the scientific article. Rely solely on the provided data and facts from the text of the article. Avoid assumptions and conjectures if information is missing. Structure the review as follows:

1. Title: Briefly. What is paper title?

2. Affiliations: What organizations are in the authors affiliations?

3. Problem: Briefly, in less than 15 words. What problem are the authors solving?

4. Results: Briefly. Describe the main results.

5. Methods: Briefly. Describe what the authors suggested.

6. Model: Briefly. The architecture of the model. The number of parameters.

7. Data: Briefly. What datasets were used in this paper?

8. Strengths: Briefly. What are the advantages of the proposed method?

9. Weaknesses: Briefly. What are the disadvantages of the proposed method?

10. Computational resources. Briefly. Give me specific numbers.
How many GPUs were used in the work? How many GPU hours were used for training?

Follow the order and names of the points. Don't number the items. Highlight the title of each item in bold. Add new line after each item.
Answer in English.
"""

    # paper_link = 'https://arxiv.org/pdf/2501.00544'

    tbot = TelegramBot()
    # review_text, error_text = giga_review(model, SYSTEM_PROMPT_EN, paper_link)
    review_text, error_text = "test", None

    if review_text is not None:
        review_text_escaped = review_text.replace('.', '\\.').replace('-', '\\-').replace('_', '\\_').replace('**', '*')

        resp = tbot.send_message(chat_id=-4615588701, message=review_text_escaped)
        print(resp.json())
    else:
        tbot.send_message(chat_id=-4615588701, message=error_text)

    return {
        'statusCode': 200,
        'body': '',
    }

if __name__ == "__main__":

    handler(None, None)
