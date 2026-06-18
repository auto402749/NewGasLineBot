from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, StickerSendMessage

import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# ── Line Bot 設定（從環境變數讀取，不要寫死在程式裡）──
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

# ── Supabase PostgreSQL 連線（從環境變數讀取）──
# 環境變數名稱：DATABASE_URL
# 格式：postgresql://USER:PASSWORD@HOST:PORT/DBNAME
def get_db_conn():
    return psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require')

# ── 初始化資料表（第一次啟動時自動建立）──
def init_db():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()

init_db()

# ── 讀取所有訂閱者 ──
def get_subscribers():
    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM subscribers")
            return [row['user_id'] for row in cur.fetchall()]

# ── 新增訂閱者 ──
def add_subscriber(user_id):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO subscribers (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (user_id,)
            )
        conn.commit()

# ── 移除訂閱者 ──
def remove_subscriber(user_id):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM subscribers WHERE user_id = %s", (user_id,))
        conn.commit()

# ── 檢查是否已訂閱 ──
def is_subscribed(user_id):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM subscribers WHERE user_id = %s", (user_id,))
            return cur.fetchone() is not None

# ── LINE Webhook 路由 ──
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ── 訊息處理 ──
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    mtext = event.message.text.strip()
    user_id = event.source.user_id

    if mtext == "綁定":
        if not is_subscribed(user_id):
            add_subscriber(user_id)
            reply = "已成功綁定，每周日13:30將自動接收油價資訊！"
        else:
            reply = "你已經綁定過了！"

    elif mtext == "解除綁定":
        if is_subscribed(user_id):
            remove_subscriber(user_id)
            reply = "已解除綁定，不再接收油價推播！"
        else:
            reply = "你尚未綁定！"

    else:
        reply = "輸入「綁定」即可訂閱油價自動推播\n輸入「解除綁定」取消"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))


if __name__ == '__main__':
    app.run()
