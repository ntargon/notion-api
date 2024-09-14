import requests
from pprint import pprint
import click
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv


# 環境変数を`.env`から読み込む
load_dotenv()


NOTION_API_KEY = os.getenv('NOTION_API_KEY', '')
DATABASE_ID = os.getenv('DATABASE_ID', '')
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

# def create_task(title: str, due_date: datetime):
#     """
#     notionにタスクを追加する
#     """

#     json_data = {
#         'parent': { 'database_id': DATABASE_ID },
#         'properties': {
#             'タスク名': {
#                 'title': [
#                     {
#                         'text': {
#                             'content': title
#                         }
#                     }
#                 ]
#             },
#             '期限': {
#                 "date": {
#                     "start": due_date.strftime('%Y-%m-%d')
#                 }
#             }
#         },
#     }

#     # データ作成
#     response = requests.post(URL_PAGES, headers=NOTION_API_HEADER, json=json_data)
#     print(response)


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

def main():
    cli()

if __name__ == "__main__":
    main()
