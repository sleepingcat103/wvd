import requests
import argparse
import threading
import time
from threading import Thread

# Telegram API 資訊 (可由命令行參數覆蓋)
bot_token = ""
chat_id = ""

class TelegramBot:
    def __init__(self):
        self.token = bot_token
        self.chat_id = int(chat_id) if chat_id else None
        # Telegram API URL
        self.api_url = f"https://api.telegram.org/bot{self.token}/" if self.token else None
        self.offset = 0
        self.msg_handlers = []

        # 在初始化時，自動設定好 offset
        if self.token and self.chat_id:
            self.initialize_offset()

    def _call_api(self, api_method, http_method='GET', params=None):
        if not self.token or not self.chat_id:
            return

        """一個私有方法，用來處理所有 API 呼叫"""
        url = f"{self.api_url}{api_method}"
        try:
            response = requests.request(http_method, url, params=params, timeout=15)
            response.raise_for_status() # 如果請求失敗，拋出異常
            return response.json().get('result', [])
        except requests.exceptions.RequestException as e:
            # print('tg request fail', e)
            return None

    def initialize_offset(self):
        """
        透過取得大量更新來設定 offset，確保從最新的訊息開始接收。
        """
        # 呼叫 getUpdates，將 limit 設為 1，但 offset 設為 -1 來取得最後一筆訊息
        # 這種方式雖然有效，但有時可能無法取得所有未讀訊息。
        # 更穩健的做法是先取得所有未讀訊息，然後設定 offset
        updates = self._call_api("getUpdates", http_method='get', params={'limit': 1, 'offset': -1})

        if updates:
            # 取得最後一筆訊息的 update_id，然後將 offset 設為 update_id + 1
            last_update_id = updates[0]['update_id']
            self.offset = last_update_id + 1

    def check_message_and_chat_id(self, update, message):
        if (update.get('message') and
            update['message'].get('text') and
            self.chat_id == int(update['message']['chat']['id']) ):
            return message == update['message']['text']
        else:
            return False

    def get_latest_update(self):
        """
        每次呼叫時，只抓取一筆最新的訊息。
        """
        if not self.token or not self.chat_id:
            return

        # 使用目前的 offset，並將 limit 設為 1，只取一筆
        params = {'offset': self.offset, 'limit': 1, 'timeout': 10}
        updates = self._call_api("getUpdates", http_method='get', params=params)

        if updates:
            update = updates[0]
            # 更新 offset 為這筆新訊息的 update_id + 1
            self.offset = update['update_id'] + 1

            for handler in self.msg_handlers:
                check_fn, action_fn = handler
                if check_fn(update):
                    action_fn()

    def send_message(self, message_text):
        """
        發送訊息
        """
        if not self.token or not self.chat_id:
            return

        params = {
            "chat_id": self.chat_id,
            "text": message_text,
            "parse_mode": "HTML" # 可以使用 HTML 或 Markdown 格式
        }
        response = self._call_api("sendMessage", http_method='post', params=params)
        return response

    def add_message_handler(self, check_fn, action_fn):
        self.msg_handlers.append((check_fn, action_fn))

# 初始化 Bot
bot = TelegramBot()


# ============= 以下是 Telegram 啟動主程序 =============

def parse_args():
    """解析命令行參數"""
    parser = argparse.ArgumentParser(description='WvDAS Telegram控制模式')

    # Telegram Bot Token
    parser.add_argument(
        '-token',
        '--token',
        type=str,
        default=None,
        help='Telegram Bot Token'
    )

    # Telegram Chat ID
    parser.add_argument(
        '-chat-id',
        '--chat-id',
        type=str,
        default=None,
        help='Telegram Chat ID'
    )

    # 添加可選的config_path參數
    parser.add_argument(
        '-config',
        '--config',
        type=str,
        default=None,
        help='配置文件路徑 (例如: c:/config.json)'
    )

    return parser.parse_args()


def start_telegram_polling(controller):
    """
    在獨立線程中持續輪詢 Telegram 更新
    """
    if not bot.token or not bot.chat_id:
        print("Telegram bot 未配置 (bot_token 或 chat_id 為空)，跳過 Telegram 輪詢")
        return

    print("Telegram bot 已啟動，開始監聽訊息...")

    # 定義接收 TG 任務訊號
    def check_pause_quest(tg_update):
        return bot.check_message_and_chat_id(tg_update, '/farm_pause')

    def check_continue_quest(tg_update):
        return bot.check_message_and_chat_id(tg_update, '/farm_continue')

    def fn_pause_quest():
        bot.send_message('嘗試停止任務')
        print('從 Telegram 收到信號：暫停任務')
        controller.msg_queue.put(('stop_quest', None))

    def fn_continue_quest():
        bot.send_message('嘗試啟動任務')
        print('從 Telegram 收到信號：啟動任務')
        # 需要重新載入設定
        from script import FarmConfig, CONFIG_VAR_LIST
        from utils import LoadConfigFromFile

        setting = FarmConfig()
        config = LoadConfigFromFile(args.config)
        for _, _, var_config_name, _ in CONFIG_VAR_LIST:
            if var_config_name in config:
                setattr(setting, var_config_name, config[var_config_name])

        controller.msg_queue.put(('start_quest', setting))

    # 註冊處理器
    bot.add_message_handler(check_pause_quest, fn_pause_quest)
    bot.add_message_handler(check_continue_quest, fn_continue_quest)

    # 持續輪詢
    while True:
        try:
            bot.get_latest_update()
            time.sleep(1)  # 每秒檢查一次
        except Exception as e:
            print(f"Telegram 輪詢錯誤: {e}")
            time.sleep(5)  # 錯誤時等待5秒再試


def main():
    global args, bot, bot_token, chat_id
    args = parse_args()

    # 如果命令行提供了 token 和 chat_id，則覆蓋全局變數
    if args.token:
        bot_token = args.token
    if args.chat_id:
        chat_id = args.chat_id

    # 重新初始化 bot
    bot = TelegramBot()

    # 導入 main.py 的 AppController
    from main import AppController

    print("=" * 50)
    print("WvDAS Telegram 控制模式")
    print("=" * 50)

    if bot.token and bot.chat_id:
        print(f"Telegram Bot 已配置")
        print(f"Chat ID: {bot.chat_id}")
        print("支援指令: /farm_pause, /farm_continue")
    else:
        print("警告: Telegram Bot 未配置 (bot_token 或 chat_id 為空)")
        print("程式將以 headless 模式運行，但無 Telegram 控制功能")

    print("=" * 50)

    # 以 headless 模式啟動 AppController
    controller = AppController(headless=True, config_path=args.config)

    # 啟動 Telegram 輪詢線程
    telegram_thread = Thread(target=start_telegram_polling, args=(controller,), daemon=True)
    telegram_thread.start()

    # 運行主循環
    try:
        controller.mainloop()
    except KeyboardInterrupt:
        print("\n收到中斷信號，正在關閉...")
        if bot.token and bot.chat_id:
            bot.send_message("WvDAS 已停止運行")


if __name__ == "__main__":
    main()
