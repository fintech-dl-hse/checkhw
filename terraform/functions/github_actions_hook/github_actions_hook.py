import os
import ydb
import ydb.iam

import hashlib
import hmac

import json

# Create driver in global space.
driver = ydb.Driver(
  endpoint=os.getenv('YDB_ENDPOINT'),
  database=os.getenv('YDB_DATABASE'),
  credentials=ydb.iam.MetadataUrlCredentials(),
)

hithub_webhook_secret_token = os.getenv('HITHUB_WEBHOOK_SECRET_TOKEN')


# Wait for the driver to become active for requests.

driver.wait(fail_fast=True, timeout=5)

# Create the session pool instance to manage YDB sessions.
pool = ydb.QuerySessionPool(driver)


def verify_signature(payload_body, secret_token, signature_header):
    """Verify that the payload was sent from GitHub by validating SHA256.

    Raise and return 403 if not authorized.

    Args:
        payload_body: original request body to verify (request.body())
        secret_token: GitHub app webhook token (WEBHOOK_SECRET)
        signature_header: header received from GitHub (x-hub-signature-256)
    """
    if not signature_header:
        print("x-hub-signature-256 header is missing!")
        return False
    hash_object = hmac.new(secret_token.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    if not hmac.compare_digest(expected_signature, signature_header):
        print("Request signatures didn't match!")
        return False

    return True

def execute_query(pool, event_data, sender, repo, check_run_summary, completed_at):
    # Create the transaction and execute query.

    placeholders = {
        '$event_data':        event_data,
        '$sender':            sender,
        '$repo':              repo,
        '$check_run_summary': check_run_summary,
        '$completed_at':      completed_at,
    }
    print("placeholders", placeholders)

    return pool.execute_with_retries(
        '''
        DECLARE $sender as UTF8;
        DECLARE $repo as UTF8;
        DECLARE $check_run_summary as UTF8;
        DECLARE $completed_at as UTF8;
        DECLARE $event_data as UTF8;

        INSERT INTO github_events_log_v2
            (
                event_data,
                event_time,
                sender,
                repo_name,
                check_run_summary,
                completed_at_str
            )
        VALUES
            (
                $event_data,
                CurrentUtcDate(),
                $sender,
                $repo,
                $check_run_summary,
                $completed_at
            );
        ''',
        placeholders
    )

def handler(event, context):
    print("event", event)

    event_body = event['body'].encode('utf-8')
    if not verify_signature(event_body, hithub_webhook_secret_token, event['headers']['X-Hub-Signature-256']):
        print("Bad signature")
        return {
            'statusCode': 404,
            'body': '',
        }

    print("Signature is ok")

    json_line = json.loads(event_body)

    # Execute query with the retry_operation helper.
    run_summary = json_line['check_run']['output']['summary']
    if run_summary is None:
        run_summary = ""

    result = execute_query(
        pool,
        event['body'],
        json_line["sender"]["login"],
        json_line["repository"]["name"],
        run_summary,
        json_line['check_run']['completed_at']
    )

    return {
        'statusCode': 200,
        'body': f'{result}',
    }
