import os
import socket
import argparse
import requests
import time
from datetime import datetime
import sys
import pytz
import logging
import traceback
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_log_fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_fmt)
logger.addHandler(_console_handler)

_file_handler = logging.FileHandler(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "teams_client.log"),
    mode="w",
)
_file_handler.setFormatter(_log_fmt)
logger.addHandler(_file_handler)


class TeamsClient:

    def __init__(self, server_ip=None, page=None):

        self.email = None
        self.passwd = None
        self.start_time = None
        self.end_time = None
        self.server_ip = server_ip
        self.tz = pytz.timezone("Asia/Kolkata")
        self.base_url = f"http://{self.server_ip}:5005"
        self.stop_signal = False

        self.prefs = {
            "profile.default_content_setting_values.media_stream_mic": 1,  # Allow microphone access
            "profile.default_content_setting_values.media_stream_camera": 1,  # Allow camera access
            "profile.default_content_setting_values.notifications": 2,  # Block notifications
            "profile.default_content_setting_values.popups": 2,  # Block pop-ups
            "profile.default_content_setting_values.geolocation": 2,  # Block geolocation
            "profile.default_content_setting_values.automatic_downloads": 2,  # Block automatic downloads
            "protocol_handler.excluded_schemes": {
                "msteams": True
            },  # Prevent "Open Microsoft Teams?" dialog
        }

        self.page = page

    def login(
        self,
    ):
        try:
            self.page.goto("https://teams.microsoft.com/v2/")
            # wait for the emailid field
            email_input = self.page.locator("#i0116")
            # enter email id into the field
            email_input.fill(self.email)

            nextButton = self.page.locator('//*[@id="idSIButton9"]')
            nextButton.click()

            # print(self.passwd)

            # wait for password field
            passElement = self.page.locator("#i0118")
            # enter password
            passElement.click()
            passElement.fill(self.passwd)

            signin = self.page.locator('//*[@id="idSIButton9"]')
            signin.click()

            yesbutton = self.page.locator('//*[@id="idSIButton9"]')
            yesbutton.click()

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            sys.exit(1)

    def check_stop_signal(self):
        """Check the stop signal from the Flask server."""
        try:
            endpoint_url = f"{self.base_url}/check_stop"

            response = requests.get(endpoint_url)  # Replace with your Flask server URL
            if response.status_code == 200:

                stop_signal_from_server = response.json().get("stop", False)

                # Only update if the server's stop signal is True
                if stop_signal_from_server:
                    self.stop_signal = True
                    logger.info(
                        "Stop signal received from the server. Exiting the loop."
                    )
                else:

                    logger.info("No stop signal received from the server. Continuing.")
            return self.stop_signal
        except Exception as e:
            logger.error(f"Error checking stop signal: {e}")

    def get_meeting_link(self):
        try:
            response = requests.get(f"{self.base_url}/meeting_link")
            if response.status_code == 200:
                data = response.json()
                self.meeting_link = data.get("meet_link")
                if not self.meeting_link:
                    logger.error("Meeting link not found in the response.")
                    sys.exit(1)
                if not self.meeting_link.startswith("https://"):
                    logger.error(
                        f"Meeting link is not a valid URL: {self.meeting_link!r}"
                    )
                    sys.exit(1)
                logger.info(f"Meeting link fetched: {self.meeting_link}")
            else:
                logger.error(
                    f"Failed to fetch meeting link. Status code: {response.status_code}"
                )
                sys.exit(1)
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            sys.exit(1)

    def enterMeeting(
        self,
    ):
        try:
            new_page = self.page.context.new_page()

            self.page = new_page

            self.page.goto(self.meeting_link, wait_until="domcontentloaded")

            self.joinfrombrowser = self.page.locator('//button[@aria-label="Join meeting from this browser"]')

            self.joinfrombrowser.evaluate("node => node.click()")
            join_meeting = self.page.locator('//*[@id="prejoin-join-button"]')

            join_meeting.evaluate("node => node.click()")

            camera_button = self.page.locator('//*[@id="video-button"]')
            camera_state = camera_button.get_attribute("data-state")
            if camera_state == "call-video-off":
                logger.info("Camera is off, enabling camera")
                camera_button.evaluate("node => node.click()")
            elif camera_state == "call-video":
                logger.info("Camera already enabled")

            mic_button = self.page.locator('//*[@id="microphone-button"]')
            mic_state = mic_button.get_attribute("data-state")
            if mic_state == "mic-off":
                logger.info("Mic is off, enabling mic")
                mic_button.evaluate("node => node.click()")
            elif mic_state == "mic":
                logger.info("Mic already enabled")
            show_more = self.page.locator(
                '//button[@id="callingButtons-showMoreBtn"]'
            )

            show_more.evaluate("node => node.click()")

            settings = self.page.locator('//div[@id="SettingsMenuControl-id"]')

            settings.evaluate("node => node.click()")

            call_health = self.page.locator('//*[@id="call-health-button"]')
            call_health.evaluate("node => node.click()")

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            sys.exit(1)

    def network_stats(
        self,
    ):
        try:
            view_more = self.page.locator(
                "//button[@data-tid='call-health-category-Network']"
            )

            view_more.click()

            self.nw_send_limit = self.page.locator(
                "//span[@data-tid='network-sent-bw-estimate']"
            ).inner_text()

            # print("=====================")
            # print(Teams_send_limit_value)

            self.nw_recevie_limit = self.page.locator(
                "//span[@data-tid='network-received-bw-estimate']"
            ).inner_text()

            self.nw_rtt = self.page.locator(
                "//span[@data-tid='network-send-rtt-avg']"
            ).inner_text()

            # it is in percentage
            self.nw_recevied_pkt_loss = self.page.locator(
                "//span[@data-tid='network-recv-loss-rate-avg']"
            ).inner_text()

            back = self.page.locator(
                "//button[@data-tid='rail-header-back-button']"
            )
            back.click()

            self.netstat_data = [
                self.nw_recevie_limit,
                self.nw_recevie_limit,
                self.nw_rtt,
                self.nw_recevied_pkt_loss,
            ]
            # print("len of netstats data",len(self.netstat_data))

            return self.netstat_data

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            sys.exit(1)

    def audio_stats(
        self,
    ):

        try:
            # print("audio")
            view_more = self.page.locator(
                "//button[@data-tid='call-health-category-Audio']"
            )
            view_more.click()

            # audio sent bitrate in Kbps
            self.au_sent_bitrate = self.page.locator(
                "//span[@data-tid='audio-send-bps']"
            ).inner_text()
            self.au_sent_bitrate = self.au_sent_bitrate.replace("Kbps", "").strip()
            if self.au_sent_bitrate and self.au_sent_bitrate != "--":
                self.au_sent_bitrate = float(self.au_sent_bitrate)
            else:
                self.au_sent_bitrate = 0.0

            # Audio sent packets
            self.au_sent_pkts = self.page.locator(
                "//span[@data-tid='audio-rtp-packets-sent']"
            ).inner_text()
            self.au_sent_pkts = self.au_sent_pkts.replace("packets", "").strip()
            if self.au_sent_pkts and self.au_sent_pkts != "--":
                self.au_sent_pkts = int(self.au_sent_pkts)
            else:
                self.au_sent_pkts = 0

            # Audio RTT in ms
            self.au_rtt = self.page.locator(
                "//span[@data-tid='audio-send-rtt-avg']"
            ).inner_text()
            self.au_rtt = self.au_rtt.replace("ms", "")
            if self.au_rtt and self.au_rtt != "--":
                self.au_rtt = float(self.au_rtt)
            else:
                self.au_rtt = 0.0

            # Audio sent codec
            self.au_sent_codec = self.page.locator(
                "//span[@data-tid='audio-send-codec']"
            ).inner_text()
            if self.au_sent_codec and self.au_sent_codec == "--":
                self.au_sent_codec = "NA"
            else:
                self.au_sent_codec = self.au_sent_codec.strip()

            # Audio Recevied Jitter
            self.au_recv_jitter = self.page.locator(
                "//span[@data-tid='audio-nw-jitter-avg']"
            ).inner_text()
            self.au_recv_jitter = self.au_recv_jitter.replace("ms", "")
            if self.au_recv_jitter and self.au_recv_jitter.strip() != "--":
                self.au_recv_jitter = float(self.au_recv_jitter)
            else:
                self.au_recv_jitter = 0.0

            # Audio recevied packets lost percentage
            self.au_recv_pkt_loss = self.page.locator(
                "//span[@data-tid='audio-recv-loss-rate-avg']"
            ).inner_text()
            self.au_recv_pkt_loss = self.au_recv_pkt_loss.replace("%", "").strip()
            if self.au_recv_pkt_loss and self.au_recv_pkt_loss != "--":
                self.au_recv_pkt_loss = float(self.au_recv_pkt_loss)
            else:
                self.au_recv_pkt_loss = 0.0

            # audio recevied packets
            self.au_recv_pkts = self.page.locator(
                "//span[@data-tid='audio-rtp-packets-received']"
            ).inner_text()
            self.au_recv_pkts = self.au_recv_pkts.replace("packets", "").strip()
            if self.au_recv_pkts and self.au_recv_pkts != "--":
                self.au_recv_pkts = int(self.au_recv_pkts)
            else:
                self.au_recv_pkts = 0

            self.au_recv_codec = self.page.locator(
                "//span[@data-tid='audio-received-codec']"
            ).inner_text()
            if self.au_recv_codec and self.au_recv_codec == "--":
                self.au_recv_codec = "NA"
            # time.sleep(3)
            back = self.page.locator(
                "//button[@data-tid='rail-header-back-button']"
            )
            back.click()

            # audio_stats_data=[self.au_sent_bitrate,self.au_sent_pkts,self.au_rtt,self.au_sent_codec,self.au_recv_jitter,self.au_recv_pkt_loss,self.au_recv_pkts,self.au_recv_codec]

            audio_stats_data = {
                "au_sent_bitrate": self.au_sent_bitrate,
                "au_sent_pkts": self.au_sent_pkts,
                "au_rtt": self.au_rtt,
                "au_sent_codec": self.au_sent_codec,
                "au_recv_jitter": self.au_recv_jitter,
                "au_recv_pkt_loss": self.au_recv_pkt_loss,
                "au_recv_pkts": self.au_recv_pkts,
                "au_recv_codec": self.au_recv_codec,
            }

            # print(audio_stats_data)
            logger.info("checking au_recevied jitter")
            logger.info(self.au_recv_jitter)
            return audio_stats_data

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            sys.exit(1)

    def video_stats(
        self,
    ):

        try:

            view_more = self.page.locator(
                "//button[@data-tid='call-health-category-Video']"
            )
            view_more.click()

            # video sent bitrate in Mbps
            self.vi_sent_bitrate = self.page.locator(
                "//span[@data-tid='video-send-current-bitrate']"
            ).inner_text()
            if self.vi_sent_bitrate and self.vi_sent_bitrate != "--":
                self.vi_sent_bitrate = self.vi_sent_bitrate.replace("Mbps", "").strip()
                self.vi_sent_bitrate = float(self.vi_sent_bitrate)
            else:
                self.vi_sent_bitrate = 0.0

            # Video received bitrate in Kbps
            self.vi_recv_bitrate = self.page.locator(
                "//span[@data-tid='video-receive-current-bitrate']"
            ).inner_text()
            if self.vi_recv_bitrate and self.vi_recv_bitrate != "--":
                self.vi_recv_bitrate = self.vi_recv_bitrate.replace("Mbps", "").strip()
                self.vi_recv_bitrate = float(self.vi_recv_bitrate)
            else:
                self.vi_recv_bitrate = 0.0

            # Video Sent frame rate in fps
            self.vi_sent_frame_rate = self.page.locator(
                "//span[@data-tid='video-send-current-frame-rate']"
            ).inner_text()
            if self.vi_sent_frame_rate and self.vi_sent_frame_rate != "--":
                self.vi_sent_frame_rate = self.vi_sent_frame_rate.replace(
                    "fps", ""
                ).strip()
                self.vi_sent_frame_rate = float(self.vi_sent_frame_rate)
            else:
                self.vi_sent_frame_rate = 0.0

            # Video sent resolution in px
            self.vi_sent_res = self.page.locator(
                "//span[@data-tid='video-send-resolution']"
            ).inner_text()
            if self.vi_sent_res and self.vi_sent_res != "--":
                self.vi_sent_res = self.vi_sent_res.replace("px", "").strip()
            else:
                self.vi_sent_res = "NA"

            # Video RTT in ms
            self.vi_rtt = self.page.locator(
                "//span[@data-tid='video-send-rtt-avg']"
            ).inner_text()
            self.vi_rtt = self.vi_rtt.replace("ms", "")
            if self.vi_rtt != "--" and self.vi_rtt:
                self.vi_rtt = float(self.vi_rtt)
            else:
                self.vi_rtt = 0.0

            # Video sent packets
            self.vi_sent_pkts = self.page.locator(
                "//span[@data-tid='video-rtp-packets-sent']"
            ).inner_text()
            if self.vi_sent_pkts and self.vi_sent_pkts != "--":
                self.vi_sent_pkts = self.vi_sent_pkts.replace("packets", "").strip()
                self.vi_sent_pkts = int(self.vi_sent_pkts)
            else:
                self.vi_sent_pkts = 0

            # video sent codec
            self.vi_sent_codec = self.page.locator(
                "//span[@data-tid='video-sent-codec-name']"
            ).inner_text()
            if self.vi_sent_codec and self.vi_sent_codec == "--":
                self.vi_sent_codec = "NA"
            else:
                self.vi_sent_codec = self.vi_sent_codec.strip()

            # Video processing type
            self.vi_processing = self.page.locator(
                "//span[@data-tid='video-processing-type']"
            ).inner_text()
            # time.sleep(3)
            back = self.page.locator(
                "//button[@data-tid='rail-header-back-button']"
            )

            back.click()

            video_stats_data = [
                self.vi_sent_bitrate,
                self.vi_recv_bitrate,
                self.vi_sent_frame_rate,
                self.vi_sent_res,
                self.vi_rtt,
                self.vi_sent_pkts,
                self.vi_sent_codec,
                self.vi_processing,
            ]
            video_stats_data = {
                "vi_sent_bitrate": self.vi_sent_bitrate,
                "vi_recv_bitrate": self.vi_recv_bitrate,
                "vi_sent_frame_rate": self.vi_sent_frame_rate,
                "vi_sent_res": self.vi_sent_res,
                "vi_rtt": self.vi_rtt,
                "vi_sent_pkts": self.vi_sent_pkts,
                "vi_sent_codec": self.vi_sent_codec,
                "vi_processing": self.vi_processing,
            }
            return video_stats_data

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            sys.exit(1)

    def get_stats_flags(self):
        endpoint_url = f"{self.base_url}/stats_opt"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                data = response.json()
                self.audio = data.get("audio_stats")
                self.video = data.get("video_stats")
            else:
                logger.warning(
                    f"Failed to fetch stats flag. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
        return None

    def get_credentials(self):
        try:
            response = requests.get(
                f"http://{self.server_ip}:5005/get_credentials", timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.email = data["email"].strip()
                self.passwd = data["password"].strip()
            else:
                logger.error(f"Failed to get credentials: {response.json().get('log')}")
                self.email = None
                self.passwd = None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during credential request: {e}")
            self.email = None
            self.passwd = None

    def get_start_and_end_time(self):
        endpoint_url = f"{self.base_url}/get_start_end_time"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                data = response.json()
                self.start_time = data.get("start_time")
                self.end_time = data.get("end_time")
            else:
                logger.warning(
                    f"Failed to fetch new login URL. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
        return None

    def send_stats_to_server(self, hostname, audio_stats, video_stats):
        if self.audio:
            payload = {
                hostname: {
                    "timestamp": datetime.now().isoformat(),
                    "audio_stats": audio_stats,
                }
            }
        if self.video:
            payload = {
                hostname: {
                    "timestamp": datetime.now().isoformat(),
                    "video_stats": video_stats,
                }
            }
        if self.audio and self.video:
            payload = {
                hostname: {
                    "timestamp": datetime.now().isoformat(),
                    "audio_stats": audio_stats,
                    "video_stats": video_stats,
                }
            }

        try:
            response = requests.post(f"{self.base_url}/upload_stats", json=payload)
            if response.status_code == 200:
                logger.info(f"Stats uploaded for {hostname}")
            else:
                logger.warning(
                    f"Failed to upload stats: {response.status_code} - {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception during upload: {e}")

    def update_participation(self):

        endpoint_url = f"{self.base_url}/set_participants_joined"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                logger.info("Device participation status updated successfully.")
            else:
                logger.warning(
                    f"Failed to update device participation status. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")


def main():
    team = None
    try:

        hostname = socket.gethostname()

        # netstats_header=['Teams Network Send Limit(Mbps)','Teams Network Receive Limit(Mbps)','Network Received Round Trip Time(ms)','Network Received Packet Loss(%)']
        # print("leng of netstat header",len(netstats_header))

        parser = argparse.ArgumentParser(description="Teams Automation")
        parser.add_argument("--ip", required=True, help="Server endpoint ip")
        parser.add_argument("--env", action="extend", nargs="+", default=[])

        args = parser.parse_args()
        for argument in args.env:
            arg = argument.split("=")
            os.environ[arg[0]] = arg[1]
        logger.info(os.environ)

        playwright = sync_playwright().start()

        browser = playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-extensions",
                "--disable-infobars",
                "--disable-popup-blocking",
                "--start-maximized",
            ],
        )
        context = browser.new_context(
            permissions=["camera","microphone"],
            no_viewport=True,
        )
        context.set_default_timeout(60 * 1000)
        page = context.pages[0] if context.pages else context.new_page()
        team = TeamsClient(server_ip=args.ip, page=page)
        team.get_meeting_link()
        team.get_stats_flags()
        team.get_credentials()
        team.login()
        time.sleep(10)
        team.enterMeeting()
        team.update_participation()
        while team.start_time is None or team.end_time is None:
            team.get_start_and_end_time()
            time.sleep(2)
        while team.start_time > datetime.now(team.tz).isoformat():
            time.sleep(2)
            logger.info("waiting for the start time")

        while team.end_time > datetime.now(team.tz).isoformat():
            logger.info("monitoring the test")
            team.check_stop_signal()
            if team.stop_signal:
                logger.info("Stop signal received. Exiting the loop.")
                break
            if team.audio:
                audio_stats = team.audio_stats()
            if team.video:
                video_stats = team.video_stats()
            if team.audio and team.video:
                team.send_stats_to_server(hostname, audio_stats, video_stats)
            elif team.audio:
                team.send_stats_to_server(hostname, audio_stats, None)
            elif team.video:
                team.send_stats_to_server(hostname, None, video_stats)
            time.sleep(1)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        browser.close()
        logger.info("Browser closed successfully.")
        playwright.stop()
        logger.info("Playwright stopped successfully.")


if __name__ == "__main__":
    main()
