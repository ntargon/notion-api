

## 環境構築

```
python -m venv .venv
pip install --upgrade pip
source .venv/bin/activate
pip install -r requirements.txt
```

## 環境変数

.envに以下を設定する

* `NOTION_API_KEY`
* `DATABASE_ID`
* `LINE_NOTIFY_TOKEN`

## コマンド

* `notify-upcoming-tasks`
  * 期日が1週間以内のタスクのうち、「完了」「アーカイブ」でないものを通知する