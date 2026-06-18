"""
push_scheduler.py
由 GitHub Actions 定時呼叫，負責：
  1. 從 Supabase 讀取所有訂閱者
  2. 爬取油價資訊
  3. 推播給所有訂閱者
"""

import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup
from linebot import LineBotApi
from linebot.models import TextSendMessage, StickerSendMessage

# ── 環境變數（在 GitHub Actions Secrets 設定）──
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
DATABASE_URL  = os.environ['DATABASE_URL']

# ── 從 Supabase 讀取所有訂閱者 ──
def get_subscribers():
    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM subscribers")
            return [row['user_id'] for row in cur.fetchall()]

# ── 爬取油價資訊 ──
def fetch_gas_info():
    gas_url = 'https://gas.goodlife.tw/'
    gas_web = requests.get(gas_url)
    gas_web.encoding = 'utf-8'
    soup = BeautifulSoup(gas_web.text, "html.parser")

    msg = ""
    updown = soup.find(id='gas-price')
    datas  = soup.find(id='cpc')

    title  = updown.find('p')
    title2 = datas.find('h2')
    msg += '\n' + title.text

    price = updown.find('h2')
    msg += price.text + '\n'
    msg += "--------------------------------------------\n"
    msg += title2.text + ":\n\n"

    items = datas.find_all('li')
    for item in items:
        h3_item = item.find("h3")
        msg += h3_item.text.strip()
        h3_item.extract()
        msg += item.text.strip() + " 元/升\n\n"

    return msg

# ── 主程式 ──
def main():
    print("開始抓取油價...")
    msg = fetch_gas_info()
    print(msg)

    subscribers = get_subscribers()
    print(f"共 {len(subscribers)} 位訂閱者")

    for user_id in subscribers:
        line_bot_api.push_message(user_id, TextSendMessage(text=msg))
        line_bot_api.push_message(user_id, StickerSendMessage(package_id='6325', sticker_id='10979917'))

    print(f"推播完成！共推播給 {len(subscribers)} 位使用者")

if __name__ == '__main__':
    main()
