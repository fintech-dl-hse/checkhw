import argparse
import datetime
import pandas as pd
import sys
import json
import os

import ydb
import ydb.iam

# Create driver in global space.
driver = ydb.Driver(
  endpoint=os.getenv('YDB_ENDPOINT'),
  database=os.getenv('YDB_DATABASE'),
  credentials=ydb.iam.MetadataUrlCredentials(),
)

# Wait for the driver to become active for requests.

driver.wait(fail_fast=True, timeout=5)

# Create the session pool instance to manage YDB sessions.
pool = ydb.QuerySessionPool(driver)


def _force_hw_grades():
    forced_grades = [
        {
            "sender": 'Vejeja',
            "max_points": 100,
            "result_points": 100,
            "homework": 'hw-activations',
            "penalty_days": 0,
            "penalty_percent": 0,
            "completed_at": datetime.datetime.now(),
        },
        {
            "sender": 'Vejeja',
            "max_points": 100,
            "result_points": 100,
            "homework": 'hw-weight-init',
            "penalty_days": 0,
            "penalty_percent": 0,
            "completed_at": datetime.datetime.now(),
        },
    ]

    return forced_grades


def _handler(event, context, detailed=False):

    accumulated_data = []

    known_homeworks = dict({
        "hw-activations": {
            "deadline": datetime.datetime.strptime("2025-02-11T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-weight-init": {
            "deadline": datetime.datetime.strptime("2025-02-11T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-optimization": {
            "deadline": datetime.datetime.strptime("2025-03-13T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-dropout": {
            "deadline": datetime.datetime.strptime("2025-03-13T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-batchnorm": {
            "deadline": datetime.datetime.strptime("2025-03-13T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-pytorch-basics": {
            "deadline": datetime.datetime.strptime("2025-03-13T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-tokenization": {
            "deadline": datetime.datetime.strptime("2025-04-17T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-rnn-attention": {
            "deadline": datetime.datetime.strptime("2025-05-22T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-transformer-attention": {
            "deadline": datetime.datetime.strptime("2025-05-22T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-llm-agent": {
            "deadline": datetime.datetime.strptime("2025-06-23T06:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-vae": {
            "deadline": datetime.datetime.strptime("2025-06-23T06:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-diffusion": {
            "deadline": datetime.datetime.strptime("2025-06-23T06:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-multimodal-llm": {
            "deadline": datetime.datetime.strptime("2025-06-23T06:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-letters": {
            "deadline": datetime.datetime.strptime("2025-06-23T06:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        # календарная дата дедлайна должна быть с запасом на 1 день больше
    })


    forced_penalty_days = {

    }

    rnn_attention_repos_whitelist = set([
        "hw-rnn-attention-DanSmirnoff",
        "hw-rnn-attention-dimontmf7",
        "hw-rnn-attention-Uritskii",
        "hw-rnn-attention-Menako778",
        "hw-rnn-attention-yellowssnake",
        "hw-rnn-attention-Ripchic",
        "hw-rnn-attention-borodulinad",
        "hw-rnn-attention-GudkovNikolay",
        "hw-rnn-attention-Dushese",
        "hw-rnn-attention-heartcatched",
        "hw-rnn-attention-anyrozh",
        "hw-rnn-attention-kultattiana",
        "hw-rnn-attention-nuotstan",
        "hw-rnn-attention-sergey-khatuntsev",
        "hw-rnn-attention-tatianasor",
        "hw-rnn-attention-chtozaserikova",
        "hw-rnn-attention-nvoronetskaya",
        "hw-rnn-attention-seemsGoodNow",
        "hw-rnn-attention-UralTime",
        "hw-rnn-attention-Astemlr",
    ])

    known_homeworks_keys = sorted(list(known_homeworks.keys()), key=lambda x: len(x), reverse=True)
    for i, hw_key_i in enumerate(known_homeworks_keys):
        for hw_key_j in known_homeworks_keys[i+1:]:
            if hw_key_i.startswith(hw_key_j) or hw_key_j.startswith(hw_key_i):
                raise Exception(f"homework names must not starts with each other {hw_key_i}, {hw_key_j}")

    query_result_set = pool.execute_with_retries('SELECT sender, repo_name, completed_at_str, check_run_summary FROM github_events_log_v2 WHERE check_run_summary != "" LIMIT 10000')
    print("len query_result_set", len(query_result_set))

    for query_result in query_result_set:
        for i, row in enumerate(query_result.rows):
            sender = row.sender
            repo_name = row.repo_name
            completed_at_str = row.completed_at_str
            check_run_summary = row.check_run_summary
            # print("i", i, "repo_name", repo_name, "sender", sender, "check_run_summary", check_run_summary)

            points = check_run_summary
            if points is None or points == "":
                # print(i, "SKIP no points summary")
                continue

            points = points.split(' ')[1]

            completed_at = datetime.datetime.strptime(completed_at_str, "%Y-%m-%dT%H:%M:%SZ")

            if sender.endswith('[bot]'):
                # print(i, "SKIP sender is bot")
                continue

            homework = None
            for homework_key in known_homeworks_keys:
                if repo_name.startswith(homework_key):
                    homework = homework_key

            if homework is None or homework not in known_homeworks:
                continue

            student_login = repo_name[len(homework)+1:]
            # print("i", i, "repo_name", repo_name, "homework", homework, "student_login", student_login)

            if repo_name.startswith("hw-rnn-attention-") and repo_name not in rnn_attention_repos_whitelist:
                # print(f"skip {repo_name}: not in whitelist for hw rnn attention")
                continue

            deadline: datetime.datetime = known_homeworks[homework]['deadline']

            penalty_days = 0

            deadline_delta = (completed_at - deadline)
            deadline_seconds = deadline_delta.total_seconds()
            if deadline_delta > datetime.timedelta(seconds=0):
                penalty_days = (deadline_seconds // 86400) + 1
                penalty_days = min(penalty_days, 3)

            if repo_name in forced_penalty_days:
                penalty_days = forced_penalty_days[repo_name]
                # print(f"use forced penalty days for {repo_name}: {penalty_days}")

            penalty_percent = penalty_days * 10
            accumulated_data.append({
                "sender": student_login,
                "max_points": int(points.split('/')[1]),
                "result_points": int(points.split('/')[0]) * (100 - penalty_percent) / 100,
                "homework": homework,
                "penalty_days": penalty_days,
                "penalty_percent": penalty_percent,
                "completed_at": completed_at,
            })

    # Hands forced grades
    accumulated_data += _force_hw_grades()

    df = pd.DataFrame(accumulated_data)

    # Sort by completion time descending to handle ties (prefer latest submission)
    # then find the index of the row with the maximum result_points for each group
    idx = df.sort_values('completed_at', ascending=False)\
            .groupby(['sender', 'homework'])['result_points']\
            .idxmax()

    # Select the rows using the obtained indices - these are the best submissions
    result_df = df.loc[idx]

    # Calculate total points using the best submissions
    result_total_df = result_df.groupby('sender')['result_points'].sum().reset_index()

    try:
        all_senders = set(result_total_df['sender'])

        placeholders = ', '.join([f'$github_nick{i}' for i in range(len(all_senders))])
        senders_fios = pool.execute_with_retries(f'SELECT github_nick, fio FROM github_nick_to_fio WHERE github_nick IN ({placeholders})', { f'$github_nick{i}': all_senders[i] for i in range(len(all_senders)) })

        senders_fios_dict = dict()
        for row in senders_fios[0].rows:
            senders_fios_dict[row.github_nick] = row.fio

        result_total_df['ФИО'] = result_total_df['sender'].map(senders_fios_dict)
    except Exception as e:
        print(f"cant set fio error: {e}")
        print(f"all_senders: {all_senders}")
        raise e

    hw_max_points = 1600
    result_total_df['hse_grade'] = result_total_df['result_points'] / hw_max_points * 10
    result_total_df['hse_grade'] = result_total_df['hse_grade'].apply(lambda x: f"{min(x, 10):.2f}")
    result_total_df['hse_grade_rounded'] = result_total_df['hse_grade'].apply(lambda x: int(float(x) + 0.5))

    df_to_render = result_total_df
    if detailed:
        df_to_render = result_df

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
        },
        'body': df_to_render.to_html(),
    }


def handler_summary(event, context):
    return _handler(event, context, detailed=False)


def handler_detailed(event, context):
    return _handler(event, context, detailed=True)


def save_nick_to_fio(event, context):

    github_nick = event['queryStringParameters']['github_nick']
    fio = event['queryStringParameters']['fio']

    # save to ydb table github_nick_to_fio
    # with replace if exists
    pool.execute_with_retries('REPLACE INTO github_nick_to_fio (github_nick, fio, created_at) VALUES ($github_nick, $fio, $created_at)', {
        '$github_nick': github_nick,
        '$fio': fio,
        '$created_at': datetime.datetime.now(),
    })

    return {
        'statusCode': 200,
        'body': 'OK',
    }
