import os
import queue
import subprocess
import sys
import tempfile
import threading
import webbrowser
from datetime import date, datetime

from auto_updater import AutoUpdater
from script import CONFIG_VAR_LIST, DUNGEON_TARGETS, Factory, LoadQuest
from utils import CHAR_LIST, LoadRawConfigFromFile, ResourcePath, SaveConfigToFile, _, logger, summary_filter


WEB_DIR = ResourcePath("web") if getattr(sys, "frozen", False) else os.path.join(os.path.dirname(__file__), "web")


def webview_storage_path():
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "_internal", "WebView2")
    return os.path.join(tempfile.gettempdir(), "wvd-webview2")


# WebView2 may create its default ``<executable>.WebView2`` directory before
# pywebview applies CreationProperties. Set the runtime override before
# importing pywebview so the profile always stays with the packaged internals.
os.environ["WEBVIEW2_USER_DATA_FOLDER"] = webview_storage_path()

import webview


def _defaults():
    return {name: default for _, name, _, default in CONFIG_VAR_LIST}


def load_config(scope="ALL"):
    raw = LoadRawConfigFromFile() or {}
    general = raw.get("GENERAL", {})
    target = general.get("FARM_TARGET")
    task = raw.get(target, {}) if general.get("TASK_SPECIFIC_CONFIG") and target else raw.get("DEFAULT", {})
    if scope == "general":
        return general
    if scope == "specific":
        return raw.get(target, {})
    if scope == "default":
        return raw.get("DEFAULT", {})
    return {**_defaults(), **general, **task}


def setting_from_dict(values):
    from script import FarmConfig
    setting = FarmConfig()
    for _, name, _, default in CONFIG_VAR_LIST:
        setattr(setting, name, values.get(name, default))
    return setting


class WebApp:
    def __init__(self, version):
        self._version = version
        self._window = None
        self._running = False
        self._setting = None
        self._worker = None
        self._update_lock = threading.Lock()
        self._messages = queue.Queue()
        self._ui_events = queue.Queue()
        self._normal_size = (1280, 820)
        self._updater = AutoUpdater(self._messages, "arnold2957", "wvd", version)
        self._log_id = logger.add(self._on_log, level="INFO", format="{time:HH:mm:ss}  {message}", enqueue=True)
        self._summary_id = logger.add(self._on_summary, level="INFO", filter=summary_filter, format="{message}", enqueue=True)

    def run(self):
        self._window = webview.create_window(
            f"WvDAS Control Center · {self._version}",
            os.path.join(WEB_DIR, "index.html"),
            js_api=self,
            width=1280,
            height=820,
            min_size=(400, 600),
            background_color="#020617",
        )
        webview.start(self._ready, debug=False, storage_path=webview_storage_path())

    def _ready(self):
        threading.Thread(target=self._message_loop, daemon=True).start()
        self.check_for_updates()

    def _check_update_worker(self):
        try:
            self._updater.check_for_updates()
        finally:
            self._update_lock.release()

    def check_for_updates(self):
        if not self._update_lock.acquire(blocking=False):
            return {"ok": False, "error": "正在檢查更新"}
        threading.Thread(target=self._check_update_worker, daemon=True).start()
        return {"ok": True}

    def _emit(self, command, value=None):
        self._ui_events.put({"command": command, "value": value})

    def poll_events(self):
        events = []
        while len(events) < 100:
            try:
                events.append(self._ui_events.get_nowait())
            except queue.Empty:
                break
        return events

    def _on_log(self, message):
        self._emit("appendLog", str(message).rstrip())

    def _on_summary(self, message):
        self._emit("setSummary", str(message).rstrip())

    def _message_loop(self):
        while True:
            try:
                command, value = self._messages.get(timeout=.25)
            except queue.Empty:
                continue
            if command == "update_available":
                raw = LoadRawConfigFromFile() or {}
                raw.setdefault("GENERAL", {})["LATEST_VERSION"] = value.get("version")
                SaveConfigToFile(raw)
                self._emit("showUpdate", value)
            elif command == "update_current":
                self._emit("updateCurrent", value)
            elif command == "update_check_failed":
                self._emit("updateCheckFailed", value)
            elif command == "download_started":
                self._emit("updateDownload", {"current": 0, "total": value})
            elif command == "progress":
                self._emit("updateDownload", {"current": value})
            elif command == "download_complete":
                self._emit("toast", {"message": "更新下載完成", "type": "success"})
            elif command == "error":
                self._emit("toast", {"message": value, "type": "error"})
            elif command == "restart_ready":
                self._emit("toast", {"message": "更新已就緒，應用程式即將重新啟動", "type": "success"})
                threading.Timer(.5, self._restart, args=(value,)).start()
            elif command == "switch_quest":
                self._switch_quest(value)

    def get_state(self):
        config = load_config()
        target = config.get("FARM_TARGET")
        task_points = self.get_task_details(target)["taskPoints"]
        return {
            "version": self._version,
            "config": config,
            "categories": DUNGEON_TARGETS,
            "characters": CHAR_LIST,
            "taskPoints": task_points,
            "running": self._running,
            "daily": self._daily_state(config),
        }

    def get_task_details(self, target):
        if not target:
            return {"taskPoints": [], "tip": ""}
        try:
            quest = LoadQuest(target)
            points = [p.target + (f" {p.roi}" if p.target == "position" else "") for p in (quest._TARGETINFOLIST or [])]
            return {"taskPoints": points, "tip": quest._TIPS or ""}
        except Exception:
            return {"taskPoints": [], "tip": ""}

    def get_changelog(self):
        try:
            with open(ResourcePath("CHANGES_LOG.md"), "r", encoding="utf-8") as file:
                return file.read()
        except OSError as error:
            logger.error(f"無法讀取更新日誌: {error}")
            return "目前無法讀取更新日誌。"

    def acknowledge_changelog(self):
        raw = LoadRawConfigFromFile() or {}
        raw.setdefault("GENERAL", {})["LAST_VERSION"] = self._version
        return {"ok": bool(SaveConfigToFile(raw))}

    def set_auto_update(self, enabled):
        raw = LoadRawConfigFromFile() or {}
        raw.setdefault("GENERAL", {})["AUTO_UPDATE"] = bool(enabled)
        return {"ok": bool(SaveConfigToFile(raw))}

    def ignore_update(self, version):
        raw = LoadRawConfigFromFile() or {}
        raw.setdefault("GENERAL", {})["IGNORED_UPDATE_VERSION"] = str(version or "")
        return {"ok": bool(SaveConfigToFile(raw))}

    def set_window_mode(self, compact):
        size = (420, 720) if compact else self._normal_size
        # Let the bridge return before touching the host window. This retains
        # the compact phone-like shape without nesting a native UI call inside
        # the JavaScript API callback.
        if self._window:
            threading.Timer(.05, self._resize_window, args=size).start()
        return {"ok": True}

    def _resize_window(self, width, height):
        try:
            self._window.resize(width, height)
        except Exception as error:
            logger.warning(f"無法調整視窗大小: {error}")

    @staticmethod
    def _daily_state(config):
        today = date.today()
        try:
            web_date = datetime.strptime(config.get("WEBSITE_ORG_TIME") or "", "%Y-%m-%d").date()
            web_due = web_date.isocalendar()[:2] != today.isocalendar()[:2]
        except ValueError:
            web_due = True
        try:
            am_date = datetime.strptime(config.get("AM_REFRESH_TIME") or "", "%Y-%m-%d").date()
            am_due = (today - date(1970, 1, 11)).days // 14 != (am_date - date(1970, 1, 11)).days // 14
        except ValueError:
            am_due = True
        return {"webDue": web_due, "amDue": am_due}

    def save(self, values):
        raw = LoadRawConfigFromFile() or {}
        general = {}
        task = {}
        for category, name, _, default in CONFIG_VAR_LIST:
            value = values.get(name, default)
            (general if category == "GENERAL" else task)[name] = value
        target = general.get("FARM_TARGET")
        result = {"GENERAL": general}
        for key, value in raw.items():
            if key != "GENERAL" and isinstance(value, dict):
                result[key] = value
        if general.get("TASK_SPECIFIC_CONFIG") and target:
            result[target] = task
        else:
            result["DEFAULT"] = task
        if not SaveConfigToFile(result):
            return {"ok": False, "error": "無法寫入 config.json"}
        return {"ok": True}

    def select_emulator(self):
        result = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=("Executable (*.exe)",))
        return result[0] if result else None

    def delete_task_config(self, target):
        raw = LoadRawConfigFromFile() or {}
        if target in raw:
            del raw[target]
        raw.setdefault("GENERAL", {})["TASK_SPECIFIC_CONFIG"] = False
        SaveConfigToFile(raw)
        return {"ok": True}

    def start_task(self, values):
        if self._running:
            return {"ok": False, "error": "任務已在執行中"}
        result = self.save(values)
        if not result["ok"]:
            return result
        self._setting = setting_from_dict(load_config())
        if not self._setting.FARM_TARGET:
            return {"ok": False, "error": "請先選擇任務目標"}
        self._setting._MSGQUEUE = self._messages
        self._setting._FORCESTOPING = threading.Event()
        self._setting._FINISHINGCALLBACK = self._finished
        self._running = True
        self._worker = threading.Thread(target=Factory(), args=(self._setting,), daemon=True)
        self._worker.start()
        logger.info(f'啟動任務「{self._setting.FARM_TARGET_TEXT}」...')
        return {"ok": True}

    def stop_task(self):
        if self._setting and self._running:
            self._setting._FORCESTOPING.set()
            logger.info("正在停止任務...")
        return {"ok": True}

    def _finished(self):
        self._running = False
        self._emit("setRunning", False)
        logger.info(_("已停止."))

    def _switch_quest(self, target):
        if not self._setting:
            return
        self._setting.FARM_TARGET = target
        self._setting.FARM_TARGET_TEXT = next((name for quests in DUNGEON_TARGETS.values() for name, code in quests.items() if code == target), target)
        self._setting._COUNTERDUNG = 0
        while self._worker and self._worker.is_alive():
            threading.Event().wait(.1)
        self._worker = threading.Thread(target=Factory(), args=(self._setting,), daemon=True)
        self._worker.start()
        self._emit("questSwitched", {"target": target, "name": self._setting.FARM_TARGET_TEXT})

    def open_url(self, url):
        if url in (
            "https://store.wizardry.info/",
            "https://webstore.wizardry.info/",
            "https://github.com/arnold2957/wvd",
            "https://github.com/arnold2957/wvd/releases",
            "https://afdian.com/a/dellyla",
        ):
            webbrowser.open(url)
            return {"ok": True}
        return {"ok": False}

    def mark_daily(self, key):
        raw = LoadRawConfigFromFile() or {}
        raw.setdefault("GENERAL", {})[key] = datetime.now().strftime("%Y-%m-%d")
        SaveConfigToFile(raw)
        return {"ok": True}

    def download_update(self):
        threading.Thread(target=self._updater.download, daemon=True).start()
        return {"ok": True}

    def _restart(self, script_path):
        threading.Event().wait(2)
        if os.name == "nt":
            subprocess.Popen([script_path], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(script_path, shell=True)
        self._window.destroy()
