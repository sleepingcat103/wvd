import requests
import argparse
import threading
import time
from threading import Thread

# Telegram API 資訊 (可由命令行參數覆蓋)
bot_token = ""
chat_id = ""
temp = {
    "config": None,
    "envs": {}
}

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
            # return message == update['message']['text']
            return update['message']['text'].startswith(message)
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
                    action_fn(update)

    def send_message(self, message_text, reply_markup=None):
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

        if reply_markup:
            import json
            params["reply_markup"] = json.dumps(reply_markup)

        response = self._call_api("sendMessage", http_method='post', params=params)
        return response

    def set_bot_commands(self):
        """
        設置 Bot 的命令選單
        """
        if not self.token or not self.chat_id:
            return

        commands = [
            {"command": "farm_pause", "description": "暫停任務"},
            {"command": "farm_continue", "description": "繼續/啟動任務"},
            {"command": "set_config", "description": "更換任務設定"},
            {"command": "set_env", "description": "設定任務config"},
        ]

        import json
        params = {
            "commands": json.dumps(commands)
        }

        response = self._call_api("setMyCommands", http_method='post', params=params)
        if response:
            self.send_message("WvDAS 控制選單已設置\n點擊選單按鈕查看可用命令")
        return response

    def add_message_handler(self, check_fn, action_fn):
        self.msg_handlers.append((check_fn, action_fn))


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

    def check_set_config(tg_update):
        return bot.check_message_and_chat_id(tg_update, '/set_config')
    
    def check_set_env(tg_update):
        return bot.check_message_and_chat_id(tg_update, '/set_env')

    def fn_pause_quest(_):
        bot.send_message('嘗試停止任務')
        print('從 Telegram 收到信號：暫停任務')
        controller.msg_queue.put(('stop_quest', None))

    def fn_continue_quest(_):
        bot.send_message('嘗試啟動任務')
        print('從 Telegram 收到信號：啟動任務')

        # 檢查是否存在現有thread，如果有則先停止
        if hasattr(controller, 'quest_threading') and controller.quest_threading and controller.quest_threading.is_alive():
            print('檢測到現有任務執行緒，先停止...')
            bot.send_message('檢測到現有任務，先停止舊任務...')
            controller.msg_queue.put(('stop_quest', None))
            # 等待thread結束
            controller.quest_threading.join(timeout=10)
            if controller.quest_threading.is_alive():
                print('警告：舊任務未能在10秒內停止')
                bot.send_message('警告：舊任務未能完全停止，仍嘗試啟動新任務')

        # 需要重新載入設定
        from script import FarmConfig, CONFIG_VAR_LIST
        from utils import LoadConfigFromFile
        global temp

        setting = FarmConfig()
        if temp["config"] != None:
            config = LoadConfigFromFile(temp["config"])
        else:
            config = LoadConfigFromFile(args.config)
            
        for _, _, var_config_name, _ in CONFIG_VAR_LIST:
            if var_config_name in config:
                setattr(setting, var_config_name, config[var_config_name])
            if var_config_name in temp["envs"]:
                setattr(setting, var_config_name, temp["envs"][var_config_name])
        
        setting._FINISHINGCALLBACK = lambda: bot.send_message("WvDAS 已暫停")

        controller.msg_queue.put(('start_quest', setting))

    def fn_set_config(update):
        msgs = update['message'].get('text').split()
        if len(msgs) > 1:
            global temp
            temp["config"] = msgs[1]
            bot.send_message(f"config set: {temp["config"]}")
        else:
            bot.send_message(f"params needed, for example:")
            bot.send_message(f"/set_config config-1.json")
    
    def fn_set_env(update):
        msgs = update['message'].get('text').split()
        if len(msgs) > 2:
            global temp
            val = None
            print(msgs[1])
            print(msgs[2])
            if msgs[1] == "_FARMTARGET":
                val = msgs[2]
                
            if msgs[1] == "_WHOWILLOPENIT":
                val = int(msgs[2])
                
            if msgs[1] == "_RESTINTERVEL":
                val = int(msgs[2])
                
            if msgs[1] == "_SKIPCOMBATRECOVER":
                val = msgs[2] == "true"
                
            if msgs[1] == "_SKIPCHESTRECOVER":
                val = msgs[2] == "true"
            
            print(val)
            if val != None:
                temp["envs"][msgs[1]] = val
                bot.send_message(f"env set: {msgs[1]} -> {val}")
                return
        
        bot.send_message(f"params needed, for example:")
        bot.send_message(f"/set_env _FARMTARGET AWD-1F")
        bot.send_message(
            f"""===== available params =====
_FARMTARGET: (AWD-1F/Scorpionesses ...etc)
_WHOWILLOPENIT: 1,2,3,4,5,6
_RESTINTERVEL: number
_SKIPCOMBATRECOVER: (true/false)
_SKIPCHESTRECOVER: (frue/false)""")
        
    # 註冊處理器
    bot.add_message_handler(check_pause_quest, fn_pause_quest)
    bot.add_message_handler(check_continue_quest, fn_continue_quest)
    bot.add_message_handler(check_set_config, fn_set_config)
    bot.add_message_handler(check_set_env, fn_set_env)

    # 設置 Bot 命令選單
    bot.set_bot_commands()

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

    # 導入 main.py 的 AppController
    from main import AppController

    print("=" * 50)
    print("WvDAS Telegram 控制模式")
    print("=" * 50)

    if bot.token and bot.chat_id:
        print(f"Telegram Bot 已配置")
        print(f"Chat ID: {bot.chat_id}")
        print("支援指令: /farm_pause, /farm_continue, /set_config, /set_env")
    else:
        print("警告: Telegram Bot 未配置 (bot_token 或 chat_id 為空)")
        print("程式將以 headless 模式運行，但無 Telegram 控制功能")

    print("=" * 50)

    # 以 headless 模式啟動 AppController
    controller = AppController(headless=True, config_path=args.config)

    from utils import RegisterTelegramHandler

    # 以下是純程式碼寫死的前綴列表，只有當訊息以其中之一開頭時才會被轉發到 Telegram
    TELEGRAM_FORWARD_PREFIXES = [
        "启动任务",
        "停止任务",
        "开始要钱",
        "ADB",
        "巫术, 启动!",
        "快快请起.",
        "即将停止脚本",
        "已完成",
        "👆向上滑动查看重要信息",
    ]

    RegisterTelegramHandler(bot.send_message, prefixes=TELEGRAM_FORWARD_PREFIXES)

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
            

args = parse_args()

# 如果命令行提供了 token 和 chat_id，則覆蓋全局變數
if args.token:
    bot_token = args.token
if args.chat_id:
    chat_id = args.chat_id
bot = TelegramBot()

if __name__ == "__main__":
    main()
