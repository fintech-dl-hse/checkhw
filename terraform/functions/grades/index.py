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
            "deadline": datetime.datetime.strptime("2025-02-10T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        "hw-weight-init": {
            "deadline": datetime.datetime.strptime("2025-02-10T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        },
        # "hw-optimization": {
        #     "deadline": datetime.datetime.strptime("2024-03-06T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-dropout": {
        #     "deadline": datetime.datetime.strptime("2024-03-06T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-batchnorm": {
        #     "deadline": datetime.datetime.strptime("2024-03-06T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-pytorch-basics": {
        #     "deadline": datetime.datetime.strptime("2024-03-06T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-letters": {
        #     "deadline": datetime.datetime.strptime("2024-05-21T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-rnn-attention": {
        #     "deadline": datetime.datetime.strptime("2024-05-14T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-transformer-attention": {
        #     "deadline": datetime.datetime.strptime("2024-05-14T03:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-vae": {
        #     "deadline": datetime.datetime.strptime("2024-06-26T11:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-diffusion": {
        #     "deadline": datetime.datetime.strptime("2024-06-26T11:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # "hw-multimodal-llm": {
        #     "deadline": datetime.datetime.strptime("2024-06-26T11:05:00", "%Y-%m-%dT%H:%M:%S"),
        # },
        # календарная дата дедлайна должна быть с запасом на 1 день больше
    })


    forced_penalty_days = {

    }

    known_homeworks_keys = sorted(list(known_homeworks.keys()), key=lambda x: len(x), reverse=True)
    for i, hw_key_i in enumerate(known_homeworks_keys):
        for hw_key_j in known_homeworks_keys[i+1:]:
            if hw_key_i.startswith(hw_key_j) or hw_key_j.startswith(hw_key_i):
                raise Exception(f"homework names must not starts with each other {hw_key_i}, {hw_key_j}")

    query_result_set = pool.execute_with_retries('SELECT event_data FROM github_events_log_v2')
    query_result = query_result_set[0]
    for i, row in enumerate(query_result.rows):
        line = row.event_data
        try:
            json_line = json.loads(line)
        except Exception as e:
            print("Can't load json (line): ", e)
            continue

        if 'action' not in json_line:
            # print("no action in json:", json_line)
            continue

        if json_line['action'] != 'completed':
            continue

        if 'check_run' not in json_line:
            # print("idx", i)
            continue

        points = json_line['check_run']['output']['summary']
        if points is None:
            continue

        points = points.split(' ')[1]

        # gh_token = os.environ['GITHUB_ACCESS_TOKEN']
        # dlhse_github = Github(gh_token)

        # commit_sha = json_line['workflow_job']['head_sha']
        # todo check commit date

        completed_at = datetime.datetime.strptime(json_line['check_run']['completed_at'], "%Y-%m-%dT%H:%M:%SZ")

        if json_line['sender']['login'].endswith('[bot]'):
            continue

        repo_name: str = json_line["repository"]["name"]
        homework = None
        for homework_key in known_homeworks_keys:
            if repo_name.startswith(homework_key):
                homework = homework_key

        if homework is None or homework not in known_homeworks:
            print("unknown hw:", homework)
            continue

        student_login = repo_name[len(homework)+1:]
        print("repo_name", repo_name, "homework", homework, "student_login", student_login)

        deadline: datetime.datetime = known_homeworks[homework]['deadline']

        penalty_days = 0

        deadline_delta = (completed_at - deadline)
        deadline_seconds = deadline_delta.total_seconds()
        if deadline_delta > datetime.timedelta(seconds=0):
            penalty_days = (deadline_seconds // 86400) + 1
            penalty_days = min(penalty_days, 3)

        if repo_name in forced_penalty_days:
            penalty_days = forced_penalty_days[repo_name]
            print(f"use forced penalty days for {repo_name}: {penalty_days}")

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

    # with open(args.detailed_out, 'w') as f:
    #     def highlight_exellent(x: str):
    #         points_color = "color:darkgreen" if x['result_points'] == x['max_points'] else None
    #         result = []
    #         for c in x.index.to_numpy():
    #             if c == 'result_points':
    #                 if x['result_points'] == x['max_points']:
    #                     result.append("background-color:lightgreen")
    #                     continue
    #             if c in [ 'penalty_days', 'penalty_percent' ]:
    #                 if x[c] > 0:
    #                     result.append("background-color:pink")
    #                     continue
    #             result.append(None)
    #         return result
    #     # result_df = result_df.style.apply(highlight_exellent, axis=1)
    #     f.write(result_df.to_html())

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
        },
        'body': result_total_df.to_html(),
    }


def handler_summary(event, context):
    return _handler(event, context, detailed=False)


def handler_detailed(event, context):
    return _handler(event, context, detailed=True)
