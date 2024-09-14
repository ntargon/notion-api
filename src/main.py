import requests
from pprint import pprint
import click
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from croniter import croniter

# 環境変数を`.env`から読み込む
load_dotenv()


NOTION_API_KEY = os.getenv('NOTION_API_KEY', '')
DATABASE_ID = os.getenv('DATABASE_ID', '')
DATABASE_ID_RECURRING_TASK = os.getenv('DATABASE_ID_RECURRING_TASK', '')
LINE_NOTIFY_API_URL = "https://notify-api.line.me/api/notify"
LINE_NOTIFY_TOKEN = os.getenv('LINE_NOTIFY_TOKEN', '')

URL_PAGES = 'https://api.notion.com/v1/pages'
URL_DATABASES = 'https://api.notion.com/v1/databases/{database_id}/query'

NOTION_API_HEADER =  {
    'Notion-Version': '2022-06-28',
    'Authorization': f'Bearer {NOTION_API_KEY}',
    'Content-Type': 'application/json',
    }


def send_line_notify(message: str):
    """LINE Notifyを使ってメッセージを送信する"""

    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
    data = {"message": message}
    response = requests.post(LINE_NOTIFY_API_URL, headers=headers, data=data)
    response.raise_for_status()

def get_upcoming_tasks(database_id):
    """Notionから期日が1週間以内のタスクを取得する"""

    tz_jst = timezone(timedelta(hours=9))
    one_week_later = (datetime.now(tz_jst) + timedelta(days=7)).isoformat()
    query = {
        "filter": {
            "and": [
                {"property": "期限", "date": {"on_or_before": one_week_later}},
                {"property": "ステータス", "status": {"does_not_equal": "完了"}},
                {"property": "ステータス", "status": {"does_not_equal": "アーカイブ"}},
            ]
        }
    }
    response = requests.post(URL_DATABASES.format(database_id=database_id), headers=NOTION_API_HEADER, json=query)
    response.raise_for_status()
    results = response.json().get('results', [])

    tasks = [
        {
            'タスク名': result['properties']['タスク名']['title'][0]['text']['content'],
            '期限': result['properties']['期限']['date']['start'],
            'url': result['url'].replace('https', 'notion')
        }
        for result in results]
    return tasks

def get_recurring_tasks(database_id):
    """Notionから定期タスク一覧を取得する"""


    response = requests.post(URL_DATABASES.format(database_id=database_id), headers=NOTION_API_HEADER)
    response.raise_for_status()
    results = response.json().get('results', [])

    tasks = [
        {
            'タスク名': result['properties']['タスク名']['title'][0]['text']['content'],
            'cron': result['properties']['cron']['rich_text'][0]['plain_text'],
            'id': result['id'],
        }
    for result in results]


    return tasks

def get_registered_recurring_tasks(database_id: str, recurring_task_id: str):
    """1ヶ月先のタスクのうち、定期タスクの一覧を取得する"""

    tz_jst = timezone(timedelta(hours=9))
    dt_now = datetime.now(tz_jst)
    four_weeks_later = dt_now + timedelta(weeks=4)
    query = {
        "filter": {
            "and": [
                {"property": "期限", "date": {"on_or_before": four_weeks_later.isoformat()}},
                {"property": "定期タスク名", "relation": {"contains": recurring_task_id}},
            ]
        }
    }

    response = requests.post(URL_DATABASES.format(database_id=database_id), headers=NOTION_API_HEADER, json=query)
    response.raise_for_status()
    results = response.json().get('results', [])

    tasks = [
        {
            'タスク名': result['properties']['タスク名']['title'][0]['text']['content'],
            '期限': result['properties']['期限']['date']['start'],
            '定期タスクid': result['properties']['定期タスク名']['relation'][0]['id'],
        }
    for result in results]

    return tasks

def create_task(database_id: str, title: str, due_date: datetime, recurring_task_id: str):
    """
    notionにタスクを追加する
    """

    json_data = {
        'parent': { 'database_id': database_id },
        'properties': {
            'タスク名': {
                'title': [
                    {
                        'text': {
                            'content': title
                        }
                    }
                ]
            },
            '期限': {
                "date": {
                    "start": due_date.strftime('%Y-%m-%d')
                }
            },
            '定期タスク名': {
                "relation": [{
                    "id": recurring_task_id
                }]
            },
        },
    }

    # データ作成
    response = requests.post(URL_PAGES, headers=NOTION_API_HEADER, json=json_data)
    response.raise_for_status()

    click.echo(f'{title} with due date = {due_date} has been created.')


@click.group()
def cli():
    pass

def compose_message_for_upcoming_tasks(tasks):
    """期日が近いタスクのメッセージを作成する"""

    message = '\n'

    for task in tasks:
        message += f'タスク名: {task["タスク名"]}\n'
        message += f'期日　　: {task["期限"]}\n'
        message += f'リンク　: {task["url"]}\n'
        message += '\n'

    return message

@cli.command()
def notify_upcoming_tasks():
    """
    完了状態になっていないタスクの内、期日が1週間以内のタスクのリンクをLINE Notifyで通知する
    """
    tasks = get_upcoming_tasks(DATABASE_ID)
    send_line_notify(compose_message_for_upcoming_tasks(tasks))

def register_recurring_task(recurring_task):

    # 4週間先までのタスクを取得
    tasks = get_registered_recurring_tasks(DATABASE_ID, recurring_task['id'])
    # tasks = []

    tz_jst = timezone(timedelta(hours=9))
    dt_now = datetime.now(tz_jst)
    four_weeks_later = dt_now + timedelta(weeks=4)

    iter = croniter(recurring_task['cron'], dt_now)
    for _i in range(4*7): # 最大28個登録する
        dt: datetime = iter.get_next(datetime)

        if dt > four_weeks_later:
            break

        if dt.strftime('%Y-%m-%d') in [task.get('期限') for task in tasks]:
            # すでに登録されている
            continue

        create_task(DATABASE_ID,
                    f"[定期] {recurring_task['タスク名']}",
                    dt,
                    recurring_task['id'])

@cli.command()
def register_recurring_tasks():
    """1ヶ月先までの定期タスクを登録する"""
    tasks = get_recurring_tasks(DATABASE_ID_RECURRING_TASK)
    for task in tasks:
        register_recurring_task(task)

def main():
    cli()

if __name__ == "__main__":
    main()
