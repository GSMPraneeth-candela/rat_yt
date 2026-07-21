import paramiko
import os
import csv
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TransferFiles:
    def __init__(self, install_deps=False) -> None:
        self.install_deps = install_deps
        self.successful_hosts = []
        self.failed_hosts = {}
        self.successful_deps_hosts = []
        self.failed_deps_hosts = {}

    def ssh_and_transfer_files(
        self, ip_address, username, password, os_type, device_status
    ):
        if device_status == 0:
            logging.info(
                f"Skipping file transfer to {ip_address} (status: {device_status})"
            )
            return
        # Initialize structure for failed files
        self.failed_hosts.setdefault(
            ip_address, {"host_error": None, "file_errors": []}
        )

        client = None
        sftp = None
        try:
            # Initialize SSH client
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=ip_address, username=username, password=password)

            # Set remote directory based on OS type
            if os_type.lower() == "windows":
                remote_dir = r"C:\\Program Files (x86)\\LANforge-Server"
                path_sep = "\\"
                files_to_transfer = [
                    "./zoom_automation/zoom_client.py",
                    "./zoom_automation/zoom_host.py",
                    "./install_dependencies.py",
                    "./real_browser/real_browser.py",
                    "./real_browser/real_browser.bat",
                    "./youtube/youtube_stream.bat",
                    "./youtube/youtube.py",
                    "./speed_test/ookla.py",
                    "./teams_automation/teams_client.py",
                    "./teams_automation/teams_host.py",
                ]
            elif os_type.lower() == "linux":
                remote_dir = "/home/lanforge"
                path_sep = "/"
                files_to_transfer = [
                    "./zoom_automation/zoom_client.py",
                    "./zoom_automation/zoom_host.py",
                    "./zoom_automation/ctzoom.bash",
                    "./install_dependencies.py",
                    "./youtube/ctyt.bash",
                    "./youtube/youtube.py",
                    "./real_browser/real_browser.py",
                    "./real_browser/ctrb.bash",
                    "./speed_test/ookla.py",
                    "./teams_automation/teams_client.py",
                    "./teams_automation/teams_host.py",
                    "./teams_automation/ctteams.bash",
                ]
            elif os_type.lower() == "mac":
                remote_dir = "/Users/lanforge"
                path_sep = "/"
                files_to_transfer = [
                    "./zoom_automation/zoom_client.py",
                    "./zoom_automation/zoom_host.py",
                    "./zoom_automation/ctzoom.bash",
                    "./install_dependencies.py",
                    "./youtube/ctyt.bash",
                    "./youtube/youtube.py",
                    "./youtube/adguard.zip",
                    "./real_browser/real_browser.py",
                    "./real_browser/ctrb.bash",
                    "./speed_test/ookla.py",
                    "./teams_automation/teams_client.py",
                    "./teams_automation/teams_host.py",
                    "./teams_automation/ctteams.bash",
                ]
            else:
                error_msg = f"Unsupported OS type: {os_type}"
                logging.error(error_msg)
                self.failed_hosts[ip_address]["host_error"] = error_msg
                return

            # Start SFTP for file transfer
            sftp = client.open_sftp()

            # Transfer the relevant files
            for file in files_to_transfer:
                local_path = os.path.join(os.path.dirname(__file__), file)
                remote_path = remote_dir + path_sep + os.path.basename(file)
                logging.info(f"Transferring {local_path} to {remote_path}")

                # Transfer the file via SFTP
                try:
                    sftp.put(local_path, remote_path)
                    logging.info(
                        f"  - Successfully transferred '{file}' to {ip_address}:{remote_path}"
                    )
                except (paramiko.SSHException, EOFError, OSError) as ssh_err:
                    # SSH session issue — no point trying remaining files
                    error_msg = (
                        f"SSH error transferring {file} to {ip_address}: {ssh_err}"
                    )
                    logging.error(error_msg)
                    self.failed_hosts[ip_address]["file_errors"].append(
                        (file, str(ssh_err))
                    )
                    break
                except Exception as file_transfer_error:
                    # File-specific error — try remaining files
                    error_msg = f"Failed to transfer {file} to {ip_address}: {file_transfer_error}"
                    logging.error(error_msg)
                    self.failed_hosts[ip_address]["file_errors"].append(
                        (file, str(file_transfer_error))
                    )
                    continue

            # Transfer and extract adguard.zip into remote /youtube directory
            self.transfer_and_extract_adguard(
                client, sftp, ip_address, os_type, remote_dir
            )

            # Host is successful only if BOTH conditions are clean:
            if (
                self.failed_hosts[ip_address]["host_error"] is None
                and len(self.failed_hosts[ip_address]["file_errors"]) == 0
            ):
                self.successful_hosts.append(ip_address)
                del self.failed_hosts[
                    ip_address
                ]  # remove entry, so it won't show in failed results

                if self.install_deps:
                    logging.info(
                        f"Triggering dependency installation on {ip_address} ({os_type})..."
                    )
                    if os_type.lower() == "windows":
                        install_cmd = r'cd /d "C:\Program Files (x86)\LANforge-Server" && py -u install_dependencies.py'
                    elif os_type.lower() == "linux":
                        install_cmd = (
                            f"cd /home/lanforge && SUDO_PASSWORD='{password}' python3 -u install_dependencies.py"
                        )
                    elif os_type.lower() == "mac":
                        install_cmd = (
                            "cd /Users/lanforge && python3 -u install_dependencies.py"
                        )
                    else:
                        install_cmd = None

                    if install_cmd:
                        try:
                            stdin, stdout, stderr = client.exec_command(
                                install_cmd, get_pty=True
                            )
                            print(f"\n--- Live Install Logs for {ip_address} ({os_type}) ---")
                            for line in iter(stdout.readline, ""):
                                print(f"[{ip_address}] {line}", end="", flush=True)

                            exit_status = stdout.channel.recv_exit_status()
                            if exit_status == 0:
                                logging.info(
                                    f"  - Successfully installed dependencies on {ip_address}"
                                )
                                self.successful_deps_hosts.append(ip_address)
                            else:
                                error_msg = f"Dependency installation failed on {ip_address} (exit code {exit_status})"
                                logging.error(error_msg)
                                self.failed_deps_hosts[ip_address] = error_msg
                        except Exception as dep_err:
                            error_msg = f"Error executing install_dependencies.py on {ip_address}: {dep_err}"
                            logging.error(error_msg)
                            self.failed_deps_hosts[ip_address] = error_msg

        except Exception as e:
            error_msg = f"Error while transferring files to {ip_address}: {e}"
            logging.error(error_msg)
            self.failed_hosts[ip_address]["host_error"] = error_msg

        finally:
            if sftp:
                sftp.close()
            if client:
                client.close()

    def transfer_and_extract_adguard(
        self, client, sftp, ip_address, os_type, remote_dir
    ):
        """Transfers adguard.zip to remote_dir/youtube, deletes existing adguard folder if present, and extracts the archive."""
        local_zip = os.path.join(os.path.dirname(__file__), "youtube", "adguard.zip")
        if not os.path.exists(local_zip):
            alt_zip = os.path.join(os.path.dirname(__file__), "adguard.zip")
            if os.path.exists(alt_zip):
                local_zip = alt_zip
            else:
                logging.info(
                    f"No local adguard.zip found at {local_zip}, skipping adguard extension transfer."
                )
                return

        if os_type.lower() == "windows":
            remote_youtube_dir = r"C:\Program Files (x86)\LANforge-Server\youtube"
            remote_zip = r"C:\Program Files (x86)\LANforge-Server\youtube\adguard.zip"
            client.exec_command(
                f'powershell -Command "New-Item -ItemType Directory -Force -Path \'{remote_youtube_dir}\'"'
            )
            extract_cmd = (
                f'powershell -Command "Set-Location \'{remote_youtube_dir}\'; '
                f"if (Test-Path 'adguard') {{ Remove-Item -Recurse -Force 'adguard' }}; "
                f'Expand-Archive -Path \'adguard.zip\' -DestinationPath \'.\' -Force"'
            )
        else:
            remote_youtube_dir = f"{remote_dir}/youtube"
            remote_zip = f"{remote_youtube_dir}/adguard.zip"
            client.exec_command(f"mkdir -p {remote_youtube_dir}")
            extract_cmd = (
                f"cd {remote_youtube_dir} && rm -rf adguard && unzip -o adguard.zip"
            )

        try:
            logging.info(f"Transferring {local_zip} to {ip_address}:{remote_zip}")
            sftp.put(local_zip, remote_zip)
            logging.info(f"  - Successfully transferred adguard.zip to {ip_address}")

            logging.info(f"Extracting adguard.zip on {ip_address}...")
            stdin, stdout, stderr = client.exec_command(extract_cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                logging.info(
                    f"  - Successfully extracted adguard.zip into {remote_youtube_dir} on {ip_address}"
                )
            else:
                err = stderr.read().decode("utf-8", errors="ignore")
                out = stdout.read().decode("utf-8", errors="ignore")
                logging.error(
                    f"Failed to extract adguard.zip on {ip_address} (exit code {exit_status}): {err.strip() or out.strip()}"
                )
        except Exception as e:
            logging.error(f"Error transferring/extracting adguard.zip on {ip_address}: {e}")

    def read_data_from_csv(self, csv_file):
        try:
            with open(csv_file, mode="r") as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    try:
                        ip_address = row["ip_address"].strip()
                        username = row["username"].strip()
                        password = row["password"].strip()
                        os_type = row["os_type"].strip()
                        device_status = int(row["device_status"])
                    except (KeyError, ValueError) as e:
                        logging.error(f"Skipping invalid row in CSV: {row} — {e}")
                        continue
                    self.ssh_and_transfer_files(
                        ip_address, username, password, os_type, device_status
                    )
        except FileNotFoundError:
            logging.error(f"CSV file not found: {csv_file}")

    def print_transfer_results(self):
        print("\n===================== 📦 TRANSFER SUMMARY =====================\n")

        if self.successful_hosts:
            print("✅ Successful Transfers:")
            for host in self.successful_hosts:
                print(f"  • {host}")
        else:
            print("❌ No successful transfers.")

        if self.failed_hosts:
            print("\n================== ❌ FAILED TRANSFERS ==================\n")
            for host, data in self.failed_hosts.items():
                print(f"Host: {host}")

                host_err = data.get("host_error")
                if host_err:
                    print(f"  ► Host Error: {host_err}")

                file_errors = data.get("file_errors") or []
                if file_errors:
                    print("  ► File Errors:")
                    for filename, err in file_errors:
                        print(f"      - {filename}: {err}")

                print("----------------------------------------------------------")
        else:
            print("\nNo failed transfers.")

        if self.install_deps:
            print("\n================= 🛠️ DEPENDENCY INSTALL SUMMARY =================\n")
            if self.successful_deps_hosts:
                print("✅ Successful Dependency Installations:")
                for host in self.successful_deps_hosts:
                    print(f"  • {host}")
            else:
                print("❌ No successful dependency installations.")

            if self.failed_deps_hosts:
                print("\n================ ❌ FAILED DEPENDENCY INSTALLS ================\n")
                for host, err in self.failed_deps_hosts.items():
                    print(f"Host: {host}")
                    print(f"  ► Error: {err}")
                    print("----------------------------------------------------------")
            else:
                print("\nNo failed dependency installations.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv", type=str, help="CSV file containing device details", required=True
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Execute install_dependencies.py on remote devices after file transfer",
    )
    args = parser.parse_args()

    transferfiles = TransferFiles(install_deps=args.install_deps)
    transferfiles.read_data_from_csv(args.csv)
    transferfiles.print_transfer_results()


if __name__ == "__main__":
    main()
