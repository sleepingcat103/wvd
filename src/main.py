import argparse
import queue
import threading

from script import Factory
from utils import LoadRawConfigFromFile, RegisterConsoleHandler, logger
from web_gui import WebApp, setting_from_dict


__version__ = "3.1.0"


def parse_args():
    parser = argparse.ArgumentParser(description="WvDAS 命令列參數")
    parser.add_argument("-headless", "--headless", action="store_true", help="以無頭模式執行")
    parser.add_argument("-config", "--config", default=None, help="設定檔路徑")
    return parser.parse_args()


def run_headless(config_path):
    RegisterConsoleHandler()
    raw = LoadRawConfigFromFile(config_path) or {}
    general = raw.get("GENERAL", {})
    target = general.get("FARM_TARGET")
    task = raw.get(target, {}) if general.get("TASK_SPECIFIC_CONFIG") and target else raw.get("DEFAULT", {})
    setting = setting_from_dict({**general, **task})
    setting._MSGQUEUE = queue.Queue()
    setting._FORCESTOPING = threading.Event()
    setting._FINISHINGCALLBACK = lambda: logger.info("已停止。")
    logger.info(f'WvDAS v{__version__} 啟動任務「{setting.FARM_TARGET_TEXT}」...')
    Factory()(setting)


def main():
    args = parse_args()
    if args.headless:
        run_headless(args.config)
    else:
        WebApp(__version__).run()


if __name__ == "__main__":
    main()
