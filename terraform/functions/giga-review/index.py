import re
import os
import sys
import json
import time
import requests

from gigachat import GigaChat


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

    resp = requests.post(
        "https://bbag2h4ru428rgr0tta2.containers.yandexcloud.net/",
        json=event_body,
        timeout=300,
    )

    print("resp", resp.content)

    return {
        'statusCode': 200,
        'body': '',
    }

if __name__ == "__main__":

    pass