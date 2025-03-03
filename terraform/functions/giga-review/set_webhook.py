import re
import os
import sys

import requests

if __name__ == "__main__":

    webhook_url, secret_token = sys.argv[1:]

    resp = requests.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/setWebhook",
        json={
            'url': webhook_url,
            "secret_token": secret_token,
            'drop_pending_updates': 'True',
            "ip_address": "",
            "allowed_updates": ["message"],
        },
        timeout=10,
    )

    print(resp.json())
