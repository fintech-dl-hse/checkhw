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

# Max raw exam points; 'Сумма баллов за экзамены' is scaled by this to the 0-2 exam grade.
EXAM_MAX = 2


def normalize_fio(value):
    """Canonical FIO form, shared verbatim with the bot's ingestion side.

    Steps (order matters): drop '<'/'>'/'"' -> lowercase -> e-yo fold ->
    collapse whitespace. Word order is preserved, so matching is order-sensitive.
    """
    if not value:
        return ""
    s = str(value)
    s = s.replace("<", "").replace(">", "").replace('"', "")
    s = s.lower().replace("ё", "е")  # ё -> е
    s = " ".join(s.split())
    return s


def _col_str(value):
    """Normalize a YDB text column to str.

    YDB returns Utf8 columns as str but String columns as bytes, so a plain
    .decode() crashes on the str case. Returns None for NULL.
    """
    if value is None:
        return None
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


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
            senders_fios_dict[_col_str(row.github_nick)] = _col_str(row.fio)

        print("senders_fios_dict", senders_fios_dict)
        result_total_df['fio'] = result_total_df['sender'].map(senders_fios_dict)
    except Exception as e:
        print(f"cant set fio error: {e}")
        print(f"all_senders: {all_senders}")

    # Fetched separately so a missing/broken department column can't break fio.
    senders_dept_dict = dict()
    try:
        query = f'{declare_placeholders} SELECT github_nick, department FROM github_nick_to_fio WHERE github_nick IN ({placeholders})'
        senders_dept = pool.execute_with_retries(query, senders_query_params)

        for row in senders_dept[0].rows:
            senders_dept_dict[_col_str(row.github_nick)] = _col_str(row.department)

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
    hw_grade_numeric = ratio.clip(upper=1.0) * 8.0
    result_total_df['hw_hse_grade'] = hw_grade_numeric.apply(lambda x: f"{x:.2f}")
    result_total_df['hw_hse_grade_rounded'] = result_total_df['hw_hse_grade'].apply(lambda x: int(float(x) + 0.5))

    # Exam grades: exact normalized-FIO match, each exam row used by at most one
    # student. Collisions (same normalized FIO) and orphan exam rows are reported.
    exam_sum_by_fio = {}
    try:
        exam_rows = pool.execute_with_retries('SELECT fio, exam_sum FROM exam_grades')
        for row in exam_rows[0].rows:
            if row.fio is None:
                continue
            # Normalize the stored value too, so matching is robust even if a row
            # was written un-normalized.
            fio_key = normalize_fio(_col_str(row.fio))
            if not fio_key:
                continue
            exam_sum_by_fio[fio_key] = float(row.exam_sum) if row.exam_sum is not None else 0.0
    except Exception as e:
        print(f"cant load exam_grades error: {e}")

    fio_by_sender = dict(zip(result_total_df['sender'], result_total_df['fio']))
    used_exam_fios = set()
    fio_collisions = []
    exam_sum_by_sender = {}
    for sender in sorted(fio_by_sender.keys()):
        fio = fio_by_sender[sender]
        key = normalize_fio(fio)
        if not key or key not in exam_sum_by_fio:
            continue
        if key in used_exam_fios:
            fio_collisions.append((sender, key))
            continue
        used_exam_fios.add(key)
        exam_sum_by_sender[sender] = exam_sum_by_fio[key]
    orphan_exam_fios = sorted(f for f in exam_sum_by_fio if f not in used_exam_fios)
    print("exam fio_collisions", fio_collisions)
    print("exam orphan_exam_fios", orphan_exam_fios)

    exam_grade_by_sender = {
        s: min(exam_sum_by_sender.get(s, 0.0) / EXAM_MAX, 1.0) * 2.0
        for s in result_total_df['sender']
    }
    result_total_df['exam_hse_grade'] = result_total_df['sender'].apply(
        lambda s: f"{exam_grade_by_sender.get(s, 0.0):.2f}"
    )
    # Final grade sums the exam grade with the ROUNDED homework grade.
    final_numeric = (result_total_df['hw_hse_grade_rounded'] + result_total_df['sender'].map(exam_grade_by_sender).fillna(0.0)).clip(upper=10.0)
    result_total_df['final_hse_grade'] = final_numeric.apply(lambda x: f"{x:.2f}")

    # github nicks with a final grade >= 4 but no FIO filled in - surfaced at the
    # bottom of the page so admins can chase them.
    no_fio_with_grade = []
    for sender, fio, final_grade in zip(
        result_total_df['sender'], result_total_df['fio'], final_numeric
    ):
        has_fio = not pd.isna(fio) and str(fio).strip() != ''
        if not has_fio and float(final_grade) >= 4:
            no_fio_with_grade.append(sender)
    no_fio_with_grade = sorted(s for s in no_fio_with_grade if s)

    # Data for the client-side "download CSV" button: only students with a FIO.
    export_data = []
    for sender, fio, hw_rounded, exam_g, final_g in zip(
        result_total_df['sender'],
        result_total_df['fio'],
        result_total_df['hw_hse_grade_rounded'],
        result_total_df['exam_hse_grade'],
        result_total_df['final_hse_grade'],
    ):
        if not pd.isna(fio) and str(fio).strip() != '':
            export_data.append({
                'fio': str(fio),
                'dept': senders_dept_dict.get(sender) or '-',
                'hw': str(hw_rounded),
                'exam': str(exam_g),
                'final': str(final_g),
            })

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

            base_html = '\n'.join(rows)

            # Replace department sentinel cells with a <select> + Save button.
            def _render_department_cell(match):
                github_nick = match.group(1)
                current = match.group(2) or '-'
                options_html = ''
                for option in ['-', 'ФТиАД', 'ЭАД', 'ФЭН', 'ИПИИ']:
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

    body = custom_html_render(df_to_render, detailed=detailed, result_df=result_df, known_homeworks=known_homeworks, hw_to_max_points=hw_to_max_points)

    if not detailed and (fio_collisions or orphan_exam_fios):
        body += "\n<h2>Exam matching warnings</h2>\n"
        if fio_collisions:
            body += "<p>FIO collisions (exam result already used by another student, skipped):</p>\n<ul>\n"
            for sender, key in fio_collisions:
                body += f"<li>{sender} &rarr; {key}</li>\n"
            body += "</ul>\n"
        if orphan_exam_fios:
            body += "<p>Orphan exam rows (matched no student):</p>\n<ul>\n"
            for fio_key in orphan_exam_fios:
                body += f"<li>{fio_key}</li>\n"
            body += "</ul>\n"

    if not detailed and no_fio_with_grade:
        body += "\n<h2>Студенты с оценкой ≥ 4 без заполненного ФИО</h2>\n<ul>\n"
        for sender in no_fio_with_grade:
            body += f"<li>{sender}</li>\n"
        body += "</ul>\n"

    if not detailed:
        # \\u003c keeps any '<' in a FIO from prematurely closing the script tag.
        export_json = json.dumps(export_data, ensure_ascii=False).replace('<', '\\u003c')
        export_html = (
            '<div style="margin: 20px 0;">'
            '<button onclick="downloadGradesCsv()">Скачать CSV (ФИО + оценки)</button>'
            '</div>\n'
            '<script>\n'
            f'const GRADES_EXPORT = {export_json};\n'
            'function csvCell(v){v=String(v==null?"":v);'
            'return /[",\\r\\n;]/.test(v)?\'"\'+v.replace(/"/g,\'""\')+\'"\':v;}\n'
            'function downloadGradesCsv(){\n'
            '  const rows=[["ФИО","Программа","Накоп","Экзамены","Итог"]];\n'
            '  for(const r of GRADES_EXPORT){rows.push([r.fio,r.dept,r.hw,r.exam,r.final]);}\n'
            '  const csv=rows.map(row=>row.map(csvCell).join(",")).join("\\r\\n");\n'
            '  const blob=new Blob(["\\ufeff"+csv],{type:"text/csv;charset=utf-8;"});\n'
            '  const url=URL.createObjectURL(blob);\n'
            '  const a=document.createElement("a");a.href=url;a.download="grades.csv";\n'
            '  document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);\n'
            '}\n'
            '</script>\n'
        )
        body = export_html + body

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
        },
        'body': body,
    }


def handler_summary(event, context):
    return _handler(event, context, detailed=False)


def handler_detailed(event, context):
    return _handler(event, context, detailed=True)


VALID_DEPARTMENTS = {"ФТиАД", "ЭАД", "ФЭН", "ИПИИ", "-"}


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

    # fio is a NOT NULL column, so a partial UPSERT that omits it is rejected
    # ("All not null columns should be initialized"). Read the existing row,
    # merge the changed field, and write all columns so the untouched sibling
    # (fio or department) is preserved instead of clobbered.
    existing_fio = ''
    existing_department = ''
    read_ok = True
    try:
        existing = pool.execute_with_retries('''
            DECLARE $github_nick as UTF8;
            SELECT fio, department FROM github_nick_to_fio WHERE github_nick = $github_nick;
        ''', {'$github_nick': github_nick})
        rows = existing[0].rows
        if rows:
            existing_fio = _col_str(rows[0].fio) or ''
            existing_department = _col_str(rows[0].department) or ''
    except Exception as e:
        read_ok = False
        print(f"save_user_info read existing failed: {e}")

    # A partial update relies on the existing value of the other column; if the
    # read failed, abort rather than risk overwriting it with an empty string.
    if (fio is None or department is None) and not read_ok:
        return {'statusCode': 500, 'body': 'could not read existing row; aborting to avoid clobbering'}

    final_fio = fio if fio is not None else existing_fio
    final_department = department if department is not None else existing_department
    # '-' is the "unset" sentinel, stored as empty string (rendered as '-').
    if final_department == '-':
        final_department = ''

    try:
        pool.execute_with_retries('''
            DECLARE $github_nick as UTF8;
            DECLARE $fio as UTF8;
            DECLARE $department as UTF8;

            UPSERT INTO github_nick_to_fio (github_nick, fio, department, created)
            VALUES ($github_nick, $fio, $department, CurrentUtcDate());
        ''', {
            '$github_nick': github_nick,
            '$fio': final_fio,
            '$department': final_department,
        })
    except Exception as e:
        # Surface the real YDB error instead of a generic 500 with no message.
        print(f"save_user_info failed: {e}")
        return {'statusCode': 500, 'body': f'save failed: {e}'}

    return {
        'statusCode': 200,
        'body': 'OK',
    }


def save_exam_grades(event, context):
    """Truncate + replace the exam_grades table from a token-authenticated POST.

    The bot (no direct YDB access) normalizes FIOs and POSTs
    {"rows": [{"fio": <normalized>, "exam_sum": <float>}, ...]} with the shared
    secret token as the `token` query param.
    """
    import base64

    expected_token = os.getenv('EXAM_GRADES_SECRET_TOKEN')
    params = event.get('queryStringParameters') or {}
    token = params.get('token')

    if not expected_token or token != expected_token:
        return {'statusCode': 401, 'body': 'unauthorized'}

    body = event.get('body') or ''
    if event.get('isBase64Encoded') and body:
        body = base64.b64decode(body).decode('utf-8')

    try:
        payload = json.loads(body) if body else {}
    except Exception:
        return {'statusCode': 400, 'body': 'invalid json body'}

    rows = payload.get('rows')
    if not isinstance(rows, list):
        return {'statusCode': 400, 'body': 'rows must be a list'}

    clean_rows = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        fio = normalize_fio(r.get('fio'))
        if not fio:
            continue
        try:
            exam_sum = float(r.get('exam_sum'))
        except (TypeError, ValueError):
            continue
        clean_rows.append((fio, exam_sum))

    # Truncate then replace: every upload fully supersedes the previous one.
    pool.execute_with_retries('DELETE FROM exam_grades;')
    for fio, exam_sum in clean_rows:
        pool.execute_with_retries('''
            DECLARE $fio as UTF8;
            DECLARE $exam_sum as Double;

            UPSERT INTO exam_grades (fio, exam_sum)
            VALUES ($fio, $exam_sum);
        ''', {'$fio': fio, '$exam_sum': exam_sum})

    return {
        'statusCode': 200,
        'body': json.dumps({'written': len(clean_rows)}),
    }
