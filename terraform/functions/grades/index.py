import argparse
import datetime
import re
import pandas as pd
import sys
import json
import os
from collections import OrderedDict

import ydb
import ydb.iam

import numpy as np

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
        # {
        #     "sender": 'Vejeja',
        #     "max_points": 100,
        #     "result_points": 100,
        #     "homework": 'hw-activations',
        #     "penalty_days": 0,
        #     "penalty_percent": 0,
        #     "completed_at": datetime.datetime.now(),
        # },
    ]

    return forced_grades


def _force_hw_bonuses():
    # Bonus points added on top of the student's best actual submission for the homework.
    # The resulting total for the homework may exceed max_points.
    return [
        {
            "sender": "sblenlkj",
            "homework": "hw-rnn-attention",
            "bonus_points": 50,
        },
    ]


def _load_known_homeworks():
    meta_path = os.path.join(os.path.dirname(__file__), "hw-meta.json")
    with open(meta_path, encoding="utf-8") as f:
        raw_list = json.load(f)
    known_homeworks = {}
    deadline_offset = datetime.timedelta(hours=3, minutes=5, seconds=1)
    for item in raw_list:
        hw_id = item["id"]
        deadline = datetime.datetime.strptime(item["deadline"], "%Y-%m-%dT%H:%M:%S")
        known_homeworks[hw_id] = {
            "deadline": deadline + deadline_offset,
            "bonus": item.get("bonus", False),
            "max_points": item.get("max_points", 0),
        }
    return known_homeworks


def _handler(event, context, detailed=False):

    accumulated_data = []

    known_homeworks = _load_known_homeworks()

    forced_penalty_days = {
        "hw-mlp-rakhamidullin": 0,
        "hw-activations-rakhamidullin": 0,
        "hw-weight-init-rakhamidullin": 0,
    }

    known_homeworks_keys = sorted(list(known_homeworks.keys()), key=lambda x: len(x), reverse=True)
    for i, hw_key_i in enumerate(known_homeworks_keys):
        for hw_key_j in known_homeworks_keys[i+1:]:
            if hw_key_i.startswith(hw_key_j) or hw_key_j.startswith(hw_key_i):
                raise Exception(f"homework names must not starts with each other {hw_key_i}, {hw_key_j}")

    query_result_set = pool.execute_with_retries('SELECT sender, repo_name, completed_at_str, check_run_summary FROM github_events_log_v2 WHERE check_run_summary != "" AND DateTime::GetYear(DateTime::Split(event_time)) == DateTime::GetYear(DateTime::Split(CurrentUtcDatetime())) LIMIT 10000')
    print("len query_result_set", len(query_result_set))

    hw_to_max_points = {}

    for query_result in query_result_set:
        for i, row in enumerate(query_result.rows):
            sender = row.sender
            repo_name = row.repo_name
            repo_name = repo_name.removeprefix('fintech-dl-hse-')
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
            student_login = re.sub(r'-\d+$', '', student_login)
            # print("i", i, "repo_name", repo_name, "homework", homework, "student_login", student_login)

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

            max_points = int(points.split('/')[1])
            result_points = int(points.split('/')[0]) * (100 - penalty_percent) / 100

            accumulated_data.append({
                "sender": student_login,
                "max_points": max_points,
                "result_points": result_points,
                "homework": homework,
                "penalty_days": penalty_days,
                "penalty_percent": penalty_percent,
                "completed_at": completed_at,
            })

            hw_to_max_points[homework] = max_points

    # Hands forced grades
    accumulated_data += _force_hw_grades()

    df = pd.DataFrame(accumulated_data)

    # Sort by completion time descending to handle ties (prefer latest submission)
    # then find the index of the row with the maximum result_points for each group
    idx = df.sort_values('completed_at', ascending=False)\
            .groupby(['sender', 'homework'])['result_points']\
            .idxmax()

    # Select the rows using the obtained indices - these are the best submissions
    result_df = df.loc[idx].copy()

    # Apply bonus points on top of best submission (may exceed homework max_points)
    for bonus in _force_hw_bonuses():
        sender = bonus["sender"]
        homework = bonus["homework"]
        bonus_points = bonus["bonus_points"]
        mask = (result_df['sender'] == sender) & (result_df['homework'] == homework)
        if mask.any():
            result_df.loc[mask, 'result_points'] = result_df.loc[mask, 'result_points'] + bonus_points
        else:
            hw_max_points_for_bonus = known_homeworks.get(homework, {}).get("max_points", 0)
            new_row = pd.DataFrame([{
                "sender": sender,
                "max_points": hw_max_points_for_bonus,
                "result_points": bonus_points,
                "homework": homework,
                "penalty_days": 0,
                "penalty_percent": 0,
                "completed_at": datetime.datetime.utcnow(),
            }])
            result_df = pd.concat([result_df, new_row], ignore_index=True)

    # Calculate total points using the best submissions
    result_total_df = result_df.groupby('sender')['result_points'].sum().reset_index()

    # Always initialize fio/department so rendering never KeyErrors even when
    # the YDB enrichment below fails (e.g. the department column is missing).
    result_total_df['fio'] = None
    # Department cell carries the nick + current value as a sentinel so the
    # HTML render can replace it with a <select> regardless of column order.
    result_total_df['department'] = result_total_df['sender'].apply(
        lambda nick: f"DEPTCELL::{nick}::-"
    )

    all_senders = [x for x in set(result_total_df['sender']) if x != '']
    placeholders = ', '.join([f'$github_nick{i}' for i in range(len(all_senders))])
    declare_placeholders = '\n'.join([f'DECLARE $github_nick{i} as UTF8;' for i in range(len(all_senders))])
    senders_query_params = {f'$github_nick{i}': all_senders[i] for i in range(len(all_senders))}

    try:
        query = f'{declare_placeholders} SELECT github_nick, fio FROM github_nick_to_fio WHERE github_nick IN ({placeholders})'
        senders_fios = pool.execute_with_retries(query, senders_query_params)

        senders_fios_dict = dict()
        for row in senders_fios[0].rows:
            senders_fios_dict[row.github_nick.decode('utf-8')] = row.fio.decode('utf-8') if row.fio is not None else None

        print("senders_fios_dict", senders_fios_dict)
        result_total_df['fio'] = result_total_df['sender'].map(senders_fios_dict)
    except Exception as e:
        print(f"cant set fio error: {e}")
        print(f"all_senders: {all_senders}")

    # Fetched separately so a missing/broken department column can't break fio.
    try:
        query = f'{declare_placeholders} SELECT github_nick, department FROM github_nick_to_fio WHERE github_nick IN ({placeholders})'
        senders_dept = pool.execute_with_retries(query, senders_query_params)

        senders_dept_dict = dict()
        for row in senders_dept[0].rows:
            senders_dept_dict[row.github_nick.decode('utf-8')] = row.department.decode('utf-8') if row.department is not None else None

        result_total_df['department'] = result_total_df['sender'].apply(
            lambda nick: f"DEPTCELL::{nick}::{senders_dept_dict.get(nick) or '-'}"
        )
    except Exception as e:
        print(f"cant set department error: {e}")

    hw_max_points = sum(
        meta["max_points"] for meta in known_homeworks.values()
        if not meta.get("bonus", False)
    )
    print("hw_max_points", hw_max_points)
    ratio = result_total_df['result_points'] / max(hw_max_points, 1)
    result_total_df['hse_grade'] = ratio.clip(upper=1.0) * 8.0
    result_total_df['hse_grade'] = result_total_df['hse_grade'].apply(lambda x: f"{x:.2f}")
    result_total_df['hse_grade_rounded'] = result_total_df['hse_grade'].apply(lambda x: int(float(x) + 0.5))

    df_to_render = result_total_df
    if detailed:
        df_to_render = result_df

    # Custom HTML rendering with input fields for NaN FIO values
    def custom_html_render(df, detailed=False, result_df=None, known_homeworks=None, hw_to_max_points=None):
        # Insert JavaScript function for making HTTP requests
        js_code = """
        <script>
        function updateFio(github_nick, inputId='') {
            const fioValue = inputId ?
                document.getElementById(inputId).value :
                document.getElementById('fio_' + github_nick).value;

            const url = `https://functions.yandexcloud.net/d4e6tbb4ljr32is5gi0g?github_nick=${github_nick}&fio=${encodeURIComponent(fioValue)}`;

            fetch(url)
                .then(response => {
                    if (response.ok) {
                        window.location.reload();
                    } else {
                        alert('Failed to update FIO');
                    }
                })
                .catch(error => {
                    alert('Error: ' + error);
                });
        }

        function editFio(github_nick) {
            const text = document.getElementById('fio_text_' + github_nick);
            const editButton = document.getElementById('fio_edit_' + github_nick);
            if (text) text.style.display = 'none';
            if (editButton) editButton.style.display = 'none';
            document.getElementById('fio_' + github_nick).style.display = '';
        }

        function onFioChange(github_nick) {
            const input = document.getElementById('fio_' + github_nick);
            const button = document.getElementById('fio_save_' + github_nick);
            button.style.display = (input.value !== input.dataset.original) ? '' : 'none';
        }

        function onDepartmentChange(github_nick) {
            const select = document.getElementById('dept_' + github_nick);
            const button = document.getElementById('dept_save_' + github_nick);
            button.style.display = (select.value !== select.dataset.original) ? '' : 'none';
        }

        function updateDepartment(github_nick) {
            const department = document.getElementById('dept_' + github_nick).value;

            const url = `https://functions.yandexcloud.net/d4e6tbb4ljr32is5gi0g?github_nick=${github_nick}&department=${encodeURIComponent(department)}`;

            fetch(url)
                .then(response => {
                    if (response.ok) {
                        window.location.reload();
                    } else {
                        alert('Failed to update department');
                    }
                })
                .catch(error => {
                    alert('Error: ' + error);
                });
        }
        </script>
        """

        # Add override form at the top
        override_form = """
        <div style="margin: 20px 0; padding: 15px; border: 1px solid #ccc; border-radius: 5px; background-color: #f9f9f9;">
            <h3 style="margin-top: 0;">Override FIO for any GitHub Nick</h3>
            <div style="display: flex; gap: 10px; align-items: center;">
                <div>
                    <label for="override_github_nick">GitHub Nick:</label><br>
                    <input type="text" id="override_github_nick" style="width: 200px; padding: 5px;">
                </div>
                <div>
                    <label for="override_fio">FIO:</label><br>
                    <input type="text" id="override_fio" style="width: 200px; padding: 5px;">
                </div>
                <div style="align-self: flex-end;">
                    <button onclick="updateFio(document.getElementById('override_github_nick').value, 'override_fio')" style="padding: 5px 15px; margin-bottom: 1px;">
                        Save Override
                    </button>
                </div>
            </div>
        </div>
        """

        style_css = """
        <style>
            input::placeholder {
                font-weight: bold;
                opacity: 0.3;
                color: red;
            }

            table.dataframe {
                border-collapse: collapse;
                font-family: Arial, sans-serif;
                font-size: 14px;
            }

            table.dataframe thead {
                background-color: #f2f2f2;
            }

            table.dataframe th,
            table.dataframe td {
                border: 1px solid #ccc;
                padding: 8px 12px;
                text-align: left;
            }

            table.dataframe tr:nth-child(even) {
                background-color: #fafafa;
            }

            table.dataframe tr:hover {
                background-color: #f1f1f1;
            }

            input[type="text"] {
                padding: 5px;
                font-size: 14px;
                width: 90%;
                box-sizing: border-box;
            }

            button {
                padding: 5px 10px;
                font-size: 14px;
                cursor: pointer;
                background-color: #007bff;
                border: none;
                color: white;
                border-radius: 4px;
            }

            button:hover {
                background-color: #0056b3;
            }
        </style>
        """

        base_html = style_css + df.to_html()

        # Process the HTML to make every FIO cell editable in place (and offer a
        # fill-in input where FIO is still missing). Columns render one <td> per
        # line, so we track the <td> index within each row: index 0 is the
        # github_nick (sender) column and index 2 is the fio column.
        if not detailed:
            rows = base_html.split('\n')
            td_index = -1
            github_nick = None
            for i, row in enumerate(rows):
                stripped = row.strip()
                if stripped.startswith('<tr>'):
                    td_index = -1
                    github_nick = None
                    continue
                if not stripped.startswith('<td>'):
                    continue
                td_index += 1
                cell_value = row.split('<td>', 1)[1].rsplit('</td>', 1)[0]
                if td_index == 0:  # github_nick (sender) column
                    github_nick = cell_value.strip()
                elif td_index == 2 and github_nick:  # fio column
                    if cell_value.strip() == 'NaN':
                        rows[i] = (
                            f'<td><input placeholder="FILL FIO HERE!" type="text" '
                            f'id="fio_{github_nick}" data-original="" '
                            f'oninput="onFioChange(\'{github_nick}\')" style="width: 200px;"> '
                            f'<button id="fio_save_{github_nick}" onclick="updateFio(\'{github_nick}\')" '
                            f'style="display:none;">Save</button></td>'
                        )
                    else:
                        rows[i] = (
                            f'<td><span id="fio_text_{github_nick}">{cell_value}</span> '
                            f'<button id="fio_edit_{github_nick}" onclick="editFio(\'{github_nick}\')" '
                            f'title="Edit FIO" style="background:none;border:none;padding:0 4px;'
                            f'cursor:pointer;filter:grayscale(1);opacity:0.45;font-size:14px;">✏️</button> '
                            f'<input type="text" id="fio_{github_nick}" value="{cell_value}" '
                            f'data-original="{cell_value}" oninput="onFioChange(\'{github_nick}\')" '
                            f'style="width: 200px; display:none;"> '
                            f'<button id="fio_save_{github_nick}" onclick="updateFio(\'{github_nick}\')" '
                            f'style="display:none;">Save</button></td>'
                        )

            base_html = override_form + '\n'.join(rows)

            # Replace department sentinel cells with a <select> + Save button.
            def _render_department_cell(match):
                github_nick = match.group(1)
                current = match.group(2) or '-'
                options_html = ''
                for option in ['-', 'ФТиАД', 'ЭАД']:
                    selected = ' selected' if option == current else ''
                    options_html += f'<option value="{option}"{selected}>{option}</option>'
                return (
                    f'<td><select id="dept_{github_nick}" data-original="{current}" '
                    f'onchange="onDepartmentChange(\'{github_nick}\')">{options_html}</select> '
                    f'<button id="dept_save_{github_nick}" onclick="updateDepartment(\'{github_nick}\')" '
                    f'style="display:none;">Save</button></td>'
                )

            base_html = re.sub(r'<td>DEPTCELL::(.+?)::(.*?)</td>', _render_department_cell, base_html)

            # Add statistics for filled fios
            filled_fios = df[df['fio'].notna()].shape[0]
            total_students = df.shape[0]
            base_html += f'<p></p><p>Filled FIOs: {filled_fios}/{total_students}</p><p></p>'

            # Add homework statistics table
            if result_df is not None and known_homeworks is not None:
                try:
                    stats_data = []
                    for hw_name in known_homeworks.keys():
                        hw_data = result_df[result_df['homework'] == hw_name]
                        if len(hw_data) > 0:
                            non_zero_count = (hw_data['result_points'] > 0).sum()
                            full_score_count = (hw_data['result_points'] == hw_data['max_points']).sum()
                            avg_score = hw_data['result_points'].mean()
                            max_points = hw_data['max_points'].iloc[0]
                        else:
                            non_zero_count = 0
                            full_score_count = 0
                            avg_score = 0.0
                            max_points = hw_to_max_points.get(hw_name, 0) if hw_to_max_points else 0

                        stats_data.append({
                            'homework': hw_name,
                            'students_with_points': non_zero_count,
                            'students_with_full_score': full_score_count,
                            'avg_score': f"{avg_score:.2f}" if avg_score > 0 else "0.00",
                            'max_points': max_points,
                        })

                    stats_df = pd.DataFrame(stats_data)
                    base_html += "\n<h2>Homework Statistics</h2>\n" + stats_df.to_html(index=False)
                except Exception as e:
                    print(f"cant calculate homework stats error: {e}")
        else:
            # Per homework statistics:
            # 1. Count of non zero solutions
            # 2. Count of full solutions
            try:
                df['full_solution'] = df['result_points'] == df['max_points']

                def count_non_zero_solutions(column):
                    return (column > 0).sum()

                df_stats = df.groupby('homework').agg({
                    'result_points': [count_non_zero_solutions],
                    'full_solution': ['sum']
                }).reset_index()
                df_stats.columns = ['homework', 'non_zero_solutions', 'full_solutions']
                base_html += "\n<h2>Stats</h2>\n" + df_stats.to_html()
            except Exception as e:
                print(f"cant calculate stats error: {e}")


        return js_code + base_html

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
        },
        'body': custom_html_render(df_to_render, detailed=detailed, result_df=result_df, known_homeworks=known_homeworks, hw_to_max_points=hw_to_max_points),
    }


def handler_summary(event, context):
    return _handler(event, context, detailed=False)


def handler_detailed(event, context):
    return _handler(event, context, detailed=True)


VALID_DEPARTMENTS = {"ФТиАД", "ЭАД", "-"}


def save_user_info(event, context):

    params = event['queryStringParameters'] or {}

    github_nick = params.get('github_nick')
    fio = params.get('fio')
    department = params.get('department')

    if not github_nick:
        return {'statusCode': 400, 'body': 'github_nick is required'}

    if fio is None and department is None:
        return {'statusCode': 400, 'body': 'nothing to update: provide fio and/or department'}

    if department is not None and department not in VALID_DEPARTMENTS:
        return {'statusCode': 400, 'body': f'invalid department: {department}'}

    # Build a dynamic UPSERT so only the supplied columns are written -
    # UPSERT (unlike REPLACE) leaves the sibling column untouched, letting
    # fio and department be saved independently from their own buttons.
    declares = ['DECLARE $github_nick as UTF8;']
    columns = ['github_nick']
    values = ['$github_nick']
    query_params = {'$github_nick': github_nick}

    if fio is not None:
        declares.append('DECLARE $fio as UTF8;')
        columns.append('fio')
        values.append('$fio')
        query_params['$fio'] = fio

    if department is not None:
        columns.append('department')
        if department == '-':
            # '-' is the "unset" sentinel - never persisted as a literal.
            values.append('NULL')
        else:
            declares.append('DECLARE $department as UTF8;')
            values.append('$department')
            query_params['$department'] = department

    columns.append('created')
    values.append('CurrentUtcDate()')

    query = '\n'.join(declares) + f'''
        UPSERT INTO github_nick_to_fio ({', '.join(columns)})
        VALUES ({', '.join(values)});
    '''

    pool.execute_with_retries(query, query_params)

    return {
        'statusCode': 200,
        'body': 'OK',
    }
