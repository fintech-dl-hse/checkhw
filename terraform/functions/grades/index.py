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
        # TODO tokenization
        "hw-tokenization": {
            "deadline": datetime.datetime.strptime("2025-04-17T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-rnn-attention": {
            "deadline": datetime.datetime.strptime("2025-05-22T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-transformer-attention": {
            "deadline": datetime.datetime.strptime("2025-05-22T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        # TODO llm
        "hw-vae": {
            "deadline": datetime.datetime.strptime("2025-06-17T11:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-diffusion": {
            "deadline": datetime.datetime.strptime("2025-06-17T11:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-multimodal-llm": {
            "deadline": datetime.datetime.strptime("2025-06-17T11:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-letters": {
            "deadline": datetime.datetime.strptime("2025-06-17T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        # календарная дата дедлайна должна быть с запасом на 1 день больше
    })


    forced_penalty_days = {

    }

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
                # print(i, "SKIP unknown hw:", homework)
                continue

            student_login = repo_name[len(homework)+1:]
            print("i", i, "repo_name", repo_name, "homework", homework, "student_login", student_login)

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

    df = pd.DataFrame(accumulated_data)

    result_df = df.groupby(by=['sender', 'homework']).last()

    result_total_df = df.groupby(by=['sender', 'homework']).last().reset_index().groupby('sender')['result_points'].sum().reset_index()

    hw_max_points = 2000
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
