#!/usr/bin/python3
import os
import argparse
import time
from datetime import datetime, timedelta
import requests
import re
import random
import platform
import logging
import tempfile

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_log_fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_fmt)
logger.addHandler(_console_handler)

_file_handler = logging.FileHandler(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_test.log"),
    mode="w",
)
_file_handler.setFormatter(_log_fmt)
logger.addHandler(_file_handler)


class YouTube(object):

    def __init__(self, url, resolution, host, port, duration, device_name, page):
        self.url = url
        self.resolution = resolution
        self.device_name = device_name
        self.host = host
        self.port = port
        self.page = page
        self.duration = duration
        self.dataset = []
        self.stop_signal = False

    def simulate_human_movements(self):
        try:
            x, y = (
                self.page.viewport_size["width"] // 2,
                self.page.viewport_size["height"] // 2,
            )
            for _ in range(random.randint(2, 5)):
                x += random.randint(-20, 20)
                y += random.randint(-20, 20)
                self.page.mouse.move(x, y)
                time.sleep(random.uniform(0.1, 0.3))
            logger.info("Human mouse movements simulated successfully.")
        except Exception as e:
            logger.error(f"Failed to simulate mouse movements: {e}")

    def get_video_id(self):
        return self.url.split("=")[1]

    def load_video(self):
        # Wait for any extension popups like AdGuard "Thank you" pages to open
        time.sleep(3)

        self.page.bring_to_front()
        logger.info(f"Loading URL: {self.url}")
        self.page.goto(self.url, wait_until="domcontentloaded")
        return True

    def check_stop_signal(self):
        """Check the stop signal from the Flask server."""
        try:
            endpoint_url = f"http://{self.host}:5002/check_stop"

            response = requests.get(endpoint_url, timeout=3)
            if response.status_code == 200:

                stop_signal_from_server = response.json().get("stop", False)

                # Only update if the server's stop signal is True
                if stop_signal_from_server:
                    self.stop_signal = True
                    logger.info("Stop signal received from server. Stopping playback.")
        except Exception as e:
            logger.error(f"Failed to check stop signal: {e}")

    def select_resolution(self):
        # Don't bother selecting resolution for Auto
        if self.resolution == "Auto":
            logger.info("Resolution set to Auto.")
            return True

        logger.info(f"Selecting resolution: {self.resolution}")
        time.sleep(0.2)
        sb = self.page.locator(".ytp-button.ytp-settings-button")
        sb.click()
        time.sleep(0.3)
        try:
            res = self.page.locator(".ytp-menuitem-label").all()
            for item in res:
                if item.text_content() == "Quality":
                    item.click()
                    break
        except Exception:
            logger.warning("Quality menu item not found in player settings.")
        time.sleep(0.3)
        try:
            res = self.page.locator(".ytp-menuitem-label").all()
            logger.debug(f"Available resolution menu items: {res}")
            for item in res:
                logger.debug(f"Resolution option: {item.text_content()}")
                if self.resolution in item.text_content():
                    item.click()
                    logger.info(f"Resolution set to {self.resolution}.")
                    return True
            logger.warning(
                f"Resolution '{self.resolution}' not available. Falling back to Auto."
            )
            for item in res:
                if "Auto" in item.text_content():
                    item.click()
                    logger.info("Fell back to Auto.")
                    return True
        except Exception as e:
            logger.error(f"Failed to select resolution: {e}")
            return False

    def enable_stats(self):
        self.page.wait_for_selector("#movie_player", timeout=60000)

        movie_player = self.page.locator("#movie_player")

        movie_player.hover()

        movie_player.click(button="right")
        try:
            self.page.locator(".ytp-menuitem").nth(7).click()
            return True
        except Exception:
            return False

    def get_stats(self):
        elem = self.page.locator(".html5-video-info-panel-content.ytp-sfn-content")
        raw_stats_data = elem.text_content()
        logger.info(f"RAW STATS DATA FROM DOM: {repr(raw_stats_data)}")

        stats_data = re.sub(r"\s+", "", raw_stats_data)
        logger.info(f"SANITIZED STATS DATA: {stats_data}")

        viewport_match = re.search(
            r"Viewport/Frames([\d+x]+)(?:\*[\d.]+)?/([\d]+)droppedof([\d]+)", stats_data
        )
        if not viewport_match:
            logger.warning("REGEX FAILED: Could not match Viewport/Frames pattern!")
        else:
            logger.info(f"REGEX SUCCESS: Viewport matched: {viewport_match.groups()}")

        current_optimal_res_match = re.search(
            r"Current/OptimalRes([\d@x]+)/([\d@x]+)", stats_data
        )
        if not current_optimal_res_match:
            logger.warning("REGEX FAILED: Could not match Current/OptimalRes pattern!")

        buffer_health_match = re.search(r"BufferHealth([\d.]+)s", stats_data)
        if not buffer_health_match:
            logger.warning("REGEX FAILED: Could not match BufferHealth pattern!")

        # Initialize an empty dictionary to store extracted values
        data = {}
        # Check and assign the extracted values if matches were found
        if viewport_match:
            data["Viewport"] = viewport_match.group(1)  # e.g., '1280x720'
            data["DroppedFrames"] = viewport_match.group(2)  # e.g., '0'
            data["TotalFrames"] = viewport_match.group(3)  # e.g., '3930'

        if current_optimal_res_match:
            data["CurrentRes"] = current_optimal_res_match.group(
                1
            )  # e.g., '1920x1080@60'
            data["OptimalRes"] = current_optimal_res_match.group(
                2
            )  # e.g., '1920x1080@60'

        if buffer_health_match:
            data["BufferHealth"] = buffer_health_match.group(1)

        current_time = datetime.now().strftime("%H:%M:%S")
        data["Timestamp"] = current_time

        logger.info(f"EXTRACTED DATA DICTIONARY: {data}")
        return data

    def get_video_duration(self):
        return self.page.locator(".ytp-time-duration").text_content()

    def enable_loop(self):
        movie_player = self.page.locator("#movie_player")
        movie_player.hover()

        movie_player.click(button="right")
        try:
            self.page.locator(".ytp-menuitem").first.click()
            return True
        except Exception:
            return False

    def full_screen(self):
        try:
            self.page.locator(".ytp-fullscreen-button.ytp-button").click()
        except Exception:
            logger.warning("Failed to enter full-screen mode.")

    def play(self):
        if not self.load_video():
            self.stop()
            return
        self.simulate_human_movements()

        if not self.enable_stats():
            self.stop()
            return
        if self.duration:
            if not self.enable_loop():
                self.stop()
                return

        if not self.select_resolution():
            self.stop()
            return

        self.video_duration = self.get_video_duration()
        time.sleep(1)
        logger.info(
            f"Playback started. URL: {self.url}, Duration: {self.duration} min, Resolution: {self.resolution}"
        )
        self.start()
        self.full_screen()
        if self.duration:
            end_time = datetime.now() + timedelta(minutes=self.duration)
            while datetime.now() <= end_time:
                now = datetime.now()
                time_left = end_time - now
                logger.info(
                    f"Loop check - Current time: {now.strftime('%H:%M:%S')}, End time: {end_time.strftime('%H:%M:%S')}, Time left: {time_left}"
                )

                logger.info("Calling check_stop_signal()...")
                self.check_stop_signal()
                if self.stop_signal:
                    break

                logger.info("check_stop_signal() completed. Calling get_stats()...")
                stats = self.get_stats()

                logger.info("get_stats() completed. Calling send_stats_to_api()...")
                logger.info(stats)
                self.dataset.append(stats)
                self.send_stats_to_api(stats, self.device_name)

                logger.info("send_stats_to_api() completed. Sleeping 1 sec...")
                time.sleep(1)
            stats = self.get_stats()
            self.dataset.append(stats)
            self.send_stats_to_api(stats, self.device_name, stop=True)
        else:
            time_array = self.video_duration.split(":")
            time_array = list(map(int, time_array))
            if len(time_array) == 3:
                delta = timedelta(
                    hours=time_array[0], minutes=time_array[1], seconds=time_array[2]
                )
            else:
                delta = timedelta(minutes=time_array[0], seconds=time_array[1])
            end_time = datetime.now() + timedelta(seconds=delta.total_seconds())
            while datetime.now() <= end_time:
                now = datetime.now()
                time_left = end_time - now
                logger.info(
                    f"Loop check - Current time: {now.strftime('%H:%M:%S')}, End time: {end_time.strftime('%H:%M:%S')}, Time left: {time_left}"
                )
                stats = self.get_stats()
                self.dataset.append(stats)
                self.send_stats_to_api(stats, self.device_name)
                time.sleep(1)
            stats = self.get_stats()
            self.dataset.append(stats)
            self.send_stats_to_api(stats, self.device_name, stop=True)

        logger.info("Playback finished.")
        self.stop()

    def start(self):
        play_button = self.page.locator(".ytp-play-button.ytp-button")
        if (
            play_button.get_attribute("data-title-no-tooltip") == "Play"
            or play_button.get_attribute("data-title-no-tooltip") != "Pause"
        ):
            play_button.click()

    def stop(self):
        logger.info("Closing browser driver.")
        self.page.close()
        logger.info("Browser driver closed successfully.")

    def send_stats_to_api(self, stats, device_name, stop=False):
        try:
            url = f"http://{self.host}:5002/youtube_stats"
            headers = {
                "Content-Type": "application/json",
            }
            data = {
                device_name: stats,  # Device name as the key and stats as the value
                "stop": stop,  # Stop remains as a separate key
            }

            response = requests.post(url, json=data, headers=headers, timeout=3)
            if response.status_code == 200:
                logger.info("Stats sent to API successfully.")
            else:
                logger.error(
                    f"Failed to send stats to API. Status code: {response.status_code}"
                )
        except Exception as e:
            logger.error(f"Failed to send stats to API: {e}")


def main():

    parser = argparse.ArgumentParser(
        prog="youtube.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
        Youtube streaming automation
         """,
        description="""\
NAME: youtube.py
PURPOSE: This script will open youtube over browser and play it for mentioned duration or single loop and get the reporting stats

Example:
    # for running a single loop of any url with Auto video resolution

        python3 youtube.py --url <video url>

    # for running a single loop of any url with required video quality

        python3 youtube.py --url <video url> --res <resoultion>

    # for running a video for certain amount of time

        python3 youtube.py --url <video url> --duration <duration in minuites>
    PS: If we mentioned the duration the loop option of video will be enabled automatically

    --res <resolution>
         144p
         240p
         360p
         480p
         720p
         1080p
    if resoultion is not there in options then video will play with Auto quality

    --duration <duration in minitues>
         If we mentioned the duration the loop option of video will be enabled automatically
         and if not then video will play only once

    --env <enviornment variable>=<enviornment value>
        If required to assign multiple envirnment variable just use --env key=value again for other values
        example python3 youtube.py --env python=python3 --env DISPLAY=:0
          """,
    )

    parser.add_argument(
        "--url", type=str, default="https://www.youtube.com/watch?v=4GnVDPD01as"
    )
    parser.add_argument("--res", type=str, default="Auto")
    parser.add_argument("--duration", default=0, type=int)
    parser.add_argument("--env", action="extend", nargs="+", default=[])

    parser.add_argument("--host", type=str, required=True)
    parser.add_argument("--port", type=str, default=8000)
    parser.add_argument("--device_name", type=str, required=True)

    args = parser.parse_args()

    for argument in args.env:
        arg = argument.split("=")
        os.environ[arg[0]] = arg[1]
    logger.debug(f"Environment variables: {dict(os.environ)}")
    local_adguard = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adguard")
    if os.path.exists(local_adguard):
        adguard_path = local_adguard
    elif platform.system() == "Windows":
        adguard_path = os.path.join(
            "C:\\", "Program Files (x86)", "LANforge-Server", "adguard"
        )
    elif platform.system() == "Linux":
        adguard_path = os.path.join(os.sep, "home", "lanforge", "adguard")
    elif platform.system() == "Darwin":  # macOS
        adguard_path = os.path.join(os.sep, "Users", "lanforge", "adguard")
    else:
        raise Exception("Unsupported OS")

    user_data_dir = tempfile.mkdtemp()

    playwright = sync_playwright().start()

    browser = playwright.chromium.launch_persistent_context(
        user_data_dir,
        headless=False,
        args=[
            f"--disable-extensions-except={adguard_path}",
            f"--load-extension={adguard_path}",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    )

    page = browser.pages[0] if browser.pages else browser.new_page()

    yt = YouTube(
        args.url,
        args.res,
        args.host,
        args.port,
        args.duration,
        args.device_name,
        page,
    )
    yt.play()


if __name__ == "__main__":
    main()
