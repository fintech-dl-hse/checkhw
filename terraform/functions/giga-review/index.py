import re
import os
import sys
import json
import time
import requests

from gigachat import GigaChat


SYSTEM_PROMPT_EN = """
Give a brief review of the scientific article. Rely solely on the provided data and facts from the text of the article. Avoid assumptions and conjectures if information is missing. Structure the review as follows:

1. **Title**: Briefly. What is paper title?

2. **Affiliations**: What organizations are in the authors affiliations?

3. **Problem**: Briefly, in less than 15 words. What problem are the authors solving?

4. **Results**: Briefly. Describe the main results.

5. **Methods**: Briefly. Describe what the authors suggested.

6. **Model**: Briefly. The architecture of the model. The number of parameters.

7. **Data**: Briefly. What datasets were used in this paper?

8. **Strengths**: Briefly. What are the advantages of the proposed method?

9. **Weaknesses**: Briefly. What are the disadvantages of the proposed method?

10. **Computational resources**. Briefly. Give me specific numbers.
How many GPUs were used in the work? How many GPU hours were used for training?

Follow the order and names of the points. Don't number the items. Highlight the title of each item in bold with **.
Add 2 new lines after each item.

Answer in English.
"""


def paper_link_to_file_name(paper_link):

    filename = paper_link.split('/')[-1]
    if not filename.endswith('.pdf'):
        filename = filename + '.pdf'

    return filename


def upload_to_gigachat_cloud(model, file_name, paper_bytes):

    if len(paper_bytes) > 30000000:
        print("too large file size:", len(paper_bytes), "limit is 30MB")
        return None

    gc_file = model.upload_file((file_name, paper_bytes))
    return gc_file.id_


def download_paper_pdf(paper_link):
    response = requests.get(paper_link, timeout=10)

    if response.status_code == 200:
        return response.content

    print("Failed to download file", paper_link)
    breakpoint()
    return None


def process_model_outputs(review_text: str) -> str:

    # Escaping
    tokens_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    review_text_processed = review_text.replace('.', '\\.')

    for token in tokens_to_escape:
        review_text_processed = review_text_processed.replace(token, f'\\{token}')

    # Fix formatting
    review_text_processed = re.sub(r'^(#+)\s+(.+)', r'**\2**', review_text_processed, flags=re.MULTILINE)

    return review_text_processed


def giga_review(model, prompt, paper_link):

    if '/abs/' in paper_link:
        paper_link = paper_link.replace('/abs/', '/pdf/')

    print("download paper", time.time())
    content = download_paper_pdf(paper_link)
    if content is None:
        return None, "Failed to download paper"

    file_name = paper_link_to_file_name(paper_link)

    file_id = upload_to_gigachat_cloud(model, file_name, content)
    print("run giga review", time.time())

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
    print("model returned ansver", time.time())
    print(model_output_content)

    print("\nresult total tokens:", total_tokens, "\n\n")

    return process_model_outputs(model_output_content), None


class TelegramBot():
    def __init__(self):

        self._telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', None)
        if self._telegram_bot_token is None:
            raise ValueError("TELEGRAM_BOT_TOKEN env var is required")

    def send_message(self, chat_id, message, message_thread_id=0, parse_mode='MarkdownV2', **kwargs):
        resp = requests.post(
            f"https://api.telegram.org/bot{self._telegram_bot_token}/sendMessage",
            json={
                'text': message,
                'parse_mode': parse_mode,
                'link_preview_options': {'is_disabled': True},
                'chat_id': chat_id,
                'message_thread_id': message_thread_id,
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


def handler(event, context):
    if event['headers']['X-Telegram-Bot-Api-Secret-Token'] != os.environ['TELEGRAM_BOT_WEBHOOK_SECRET_TOKEN']:
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

    event_body['X-Telegram-Bot-Api-Secret-Token'] = event['headers']['X-Telegram-Bot-Api-Secret-Token']
    print("event_body", event_body)

    resp = requests.post(
        "https://functions.yandexcloud.net/d4eekb5q97upoaot6dbf?integration=async",
        json=event_body,
        timeout=10,
    )

    if resp.status_code > 299:
        return {
            'statusCode': resp.status_code,
            'body': '',
        }

    print("resp", resp.content)

    tbot = TelegramBot()

    response_chat_id = event_body['message']['chat']['id']
    message_id = event_body['message']['message_id']
    resp = tbot.send_message_reaction(response_chat_id, message_id, "👀")
    print("response_chat_id, message_id", response_chat_id, message_id)
    print("resp", resp.content)

    return {
        'statusCode': 200,
        'body': '',
    }


def handler_async(event_body, context):

    assert os.environ['GIGACHAT_CREDENTIALS'] is not None

    gigachat_timeout = 300
    model = GigaChat(
        model="GigaChat-Pro",
        scope="GIGACHAT_API_PERS",
        verify_ssl_certs=True,
        timeout=gigachat_timeout,
    )
    import httpx
    model._client.timeout = httpx.Timeout(gigachat_timeout, connect=gigachat_timeout)
    model._auth_client.timeout = httpx.Timeout(gigachat_timeout, connect=gigachat_timeout)


    # paper_link = 'https://arxiv.org/pdf/2501.00544'

    tbot = TelegramBot()

    response_chat_id = event_body['message']['chat']['id']
    message_thread_id = event_body['message'].get('message_thread_id', 0)
    message_id = event_body['message']['message_id']

    chats_whitelist = [-1001948862463, -4615588701, -1002434078215, -4795660059]
    if response_chat_id not in chats_whitelist:
        print("BAD CHAT id", response_chat_id)
        resp = tbot.send_message_reaction(response_chat_id, message_id, "👎")
        print("resp", resp.content)
        return

    message_text = event_body['message'].get('text', '')

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

    print("command", command, "paper_link", paper_link)

    if paper_link is not None:
        print("run giga review")

        message_id = event_body['message']['message_id']
        resp = tbot.send_message_reaction(response_chat_id, message_id, "👀")
        print("response_chat_id, message_id, message_thread_id", response_chat_id, message_id, message_thread_id)
        print("resp", resp.content)

        try:
            review_text, error_text = giga_review(model, SYSTEM_PROMPT_EN, paper_link)
        except Exception as e:
            print("error", e)

            error_text = 'failed to get review: \n```\n' + str(e) + '\n```'
    else:
        error_text = "No paper link provided"

    if review_text is not None:

        resp = tbot.send_message(chat_id=response_chat_id, message_thread_id=message_thread_id, message=review_text)

        print(resp.json())

        if resp.status_code != 200:
            print("error sending message", resp.json())
            tbot.send_message(chat_id=response_chat_id, message_thread_id=message_thread_id, message=f"Error: ```{resp.json()}```")
    else:
        tbot.send_message(chat_id=response_chat_id, message_thread_id=message_thread_id, message=f"Error: ```{error_text}```")

    return

if __name__ == "__main__":

    assert os.environ['GIGACHAT_CREDENTIALS'] is not None

    telegram_bot_token = os.environ['TELEGRAM_BOT_TOKEN']

    offset = 0

    while True:
        time.sleep(2)

        try:
            resp = requests.get(f"https://api.telegram.org/bot{telegram_bot_token}/getUpdates", params={'offset': offset, "allowed_updates": '["message"]'})
            if resp.status_code != 200:
                raise ValueError("Failed to get updates", resp.content)
        except Exception as e:
            print("error getting updates:", e)
            continue

        resp_json = resp.json()
        for update in resp_json['result']:
            print("update", update)
            try:
                handler_async(update, None)
            except Exception as e:
                print("error handling update:", e)

            offset = update['update_id'] + 1
