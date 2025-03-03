
import re
import os
import sys
import json
import time
import requests

import httpx

import gigachat
from gigachat import GigaChat


assert os.environ['GIGACHAT_CREDENTIALS'] is not None

import subprocess

import os
from sanic import Sanic
from sanic.response import text

app = Sanic(__name__)

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




def paper_link_to_file_name(paper_link):

    filename = paper_link.split('/')[-1]
    if not filename.endswith('.pdf'):
        filename = filename + '.pdf'

    return filename


import requests
from typing import Any, Dict, Optional
from typing_extensions import Literal

FileTypes = Any  # Replace with actual file type if needed

def chat_gigachat(model: GigaChat, chat: dict, access_token=None):

    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    # response = requests.post(
    #     url,
    #     headers={
    #         "Authorization": f"Bearer {access_token}",
    #         "Content-Type": "application/json",
    #         "Connection": "close",
    #     },
    #     json={
    #         "model": model._settings.model,
    #         "messages": chat["messages"],
    #         "temperature": chat["temperature"],
    #     },
    #     verify=False,
    #     timeout=(120, 120),
    # )

    chat_json = {
        "model": model._settings.model,
        "messages": chat["messages"],
        "temperature": chat["temperature"],
    }

    chat_json_str = json.dumps(chat_json)

    auth_header = f"Authorization: Bearer {access_token}"

    result = subprocess.run(["curl", '--max-time', '120', "-k", url, '-H', auth_header, '-H', 'Content-Type: application/json', '-d', chat_json_str  ], capture_output=True, text=True)
    print("result", result.stdout)
    print("result", result.stdout)

    response_json = json.loads(result.stdout)

    return response_json

def upload_to_gigachat_cloud(model: GigaChat, file_name, paper_bytes, access_token=None):

    if len(paper_bytes) > 30000000:
        print("too large file size:", len(paper_bytes), "limit is 30MB")
        return None

    with open(f'./{file_name}', 'wb') as f:
        f.write(paper_bytes)


    if access_token is None:
        access_token = model.get_token().access_token


    auth_header = f"Authorization: Bearer {access_token}"

    url = "https://gigachat.devices.sberbank.ru/api/v1/files"

    result = subprocess.run(["curl", '--max-time', '120', "-k", url, '-H', auth_header, '--form', f'file=@"./{file_name}"', '--form', 'purpose="general"' ], capture_output=True, text=True)

    print("curl out upload", result.stdout)  # Prints the response body
    print("curl err upload", result.stderr)

    response_json = json.loads(result.stdout)

    return response_json['id']

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

    def send_message_reaction(self, chat_id, message_id, reaction_emoji, **kwargs):
        resp = requests.post(
            f"https://api.telegram.org/bot{self._telegram_bot_token}/setMessageReaction",
            json={
                'chat_id': chat_id,
                'message_id': message_id,
                'reaction': [{"type": "emoji", "emoji": reaction_emoji}],
                **kwargs
            },
            timeout=10,
        )

        return resp



def giga_review(model: GigaChat, prompt, paper_link, access_token=None):

    if '/abs/' in paper_link:
        paper_link = paper_link.replace('/abs/', '/pdf/')

    print("download paper", time.time())
    content = download_paper_pdf(paper_link)
    if content is None:
        return None, "Failed to download paper"

    file_name = paper_link_to_file_name(paper_link)

    import logging
    logging.basicConfig(
        format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG
    )
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


    # httpx_logger = logging.getLogger("httpx")
    # httpx_logger.setLevel(logging.DEBUG)

    # httpcore_logger = logging.getLogger("httpcore")
    # httpcore_logger.setLevel(logging.DEBUG)

    chat_text = {
        "messages": [
            {
                "role": "user",
                "content": "Who are you?",
            }
        ],
        "temperature": 0.0
    }
    # result = chat_gigachat(model, chat_text, access_token=access_token)
    # print("result", result['choices'][0]['message']['content'])

    file_id = upload_to_gigachat_cloud(model, file_name, content, access_token=access_token)
    print("run giga review", time.time())

    time.sleep(10)

    chat_text = {
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "attachments": [file_id],
            }
        ],
        "temperature": 0.0
    }

    result = chat_gigachat(model, chat_text, access_token=access_token)
    print("result", result)

    model_output_content = result['choices'][0]['message']['content']
    total_tokens = result['usage']['total_tokens']

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
    print("model returned ansver", time.time())
    print(model_output_content)

    print("\nresult total tokens:", total_tokens, "\n\n")

    return model_output_content, None



def handler_sanic(event_body, context):

    print("event_body", event_body)

    if event_body['X-Telegram-Bot-Api-Secret-Token'] != os.environ['TELEGRAM_BOT_WEBHOOK_SECRET_TOKEN']:
        print("invalid secret token")
        return {
            'statusCode': 200,
            'body': '',
        }

    assert os.environ['GIGACHAT_CREDENTIALS'] is not None

    # import http.client
    # http.client.HTTPConnection.debuglevel = 1  # Enable HTTP logs

    gigachat_timeout = 10
    model = GigaChat(
        model="GigaChat-Pro",
        scope="GIGACHAT_API_PERS",
        verify_ssl_certs=False,
        timeout=gigachat_timeout,
    )
    import httpx
    model._client.timeout = httpx.Timeout(gigachat_timeout, connect=gigachat_timeout)
    model._auth_client.timeout = httpx.Timeout(gigachat_timeout, connect=gigachat_timeout)
    model._client.limits = httpx.Limits(max_connections=1, max_keepalive_connections=0, keepalive_expiry=0.0001)
    model._auth_client.limits = httpx.Limits(max_connections=1, max_keepalive_connections=0, keepalive_expiry=0.0001)

    model._client.headers.update({"User-Agent": "curl/7.68.0", "Connection": "close"})
    model._auth_client.headers.update({"User-Agent": "curl/7.68.0", "Connection": "close"})

    access_token = model.get_token().access_token
    print("model.get_token().access_token", access_token)
    auth_header = f'Authorization: Bearer {access_token}'
    # url = "https://gigachat.devices.sberbank.ru/api/v1/models"
    # result = subprocess.run(["curl", '-v', '--max-time', '10', "-k", url, '-H', auth_header], capture_output=True, text=True)
    # print("curl out", result.stdout)  # Prints the response body

    import ssl

    print(ssl.OPENSSL_VERSION)
    # resp = requests.get(url, headers={"User-Agent": "curl/7.68.0", "Connection": "close", "Authorization": f"Bearer {access_token}"}, verify=False, timeout=(5, 5))
    # print("resp", resp.json())

    paper_link = 'https://arxiv.org/pdf/2501.00544'

    tbot = TelegramBot()

    response_chat_id = event_body['message']['chat']['id']

    message_text = event_body['message']['text']

    review_text, error_text, paper_link = None, None, None

    command_parts = message_text.split(' ')
    if len(command_parts) == 0:
        error_text = "No command provided"
    else:
        command = command_parts[0]
        if command == "/review":
            if len(command_parts) > 1:
                paper_link = command_parts[1]
            else:
                error_text = "No paper link provided"
        else:
            error_text = "Unknown command"

    if error_text is None:
        print("command", command, "paper_link", paper_link)
        review_text = 'Test ' + paper_link

        print("run giga review")
        review_text, error_text = giga_review(model, SYSTEM_PROMPT_EN, paper_link, access_token=access_token)

    if review_text is not None:
        review_text_escaped = review_text.replace('.', '\\.').replace('-', '\\-').replace('_', '\\_').replace('**', '*').replace('{', '\\{').replace('}', '\\}')

        resp = tbot.send_message(chat_id=response_chat_id, message=review_text_escaped)
        print(resp.json())
    else:
        resp = tbot.send_message(chat_id=response_chat_id, message=error_text)
        print(resp.json())

    return {
        'statusCode': 200,
        'body': '',
    }



@app.after_server_start
async def after_server_start(app, loop):
    print(f"App listening at port {os.environ['PORT']}")

@app.post("/")
def hello(request):
    handler_sanic(request.json, None)

    return text("ok")

if __name__ == "__main__":

    app.run(host='0.0.0.0', port=int(os.environ['PORT']), motd=False, access_log=False)
