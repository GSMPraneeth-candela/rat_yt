#!/usr/bin/env python3

import subprocess
import platform
import os


def main():
    print("Installing Script Python3 Dependencies")
    packages = [
        "selenium",
        "playwright",
        "requests",
        "pyperclip",
        "pytz",
        "pyautogui",
        "clipboard",
        "pandas",
        "matplotlib",
        "flask",
        "wkhtmltopdf",
        "pdfkit",
    ]
    packages_installed = []
    packages_failed = []

    for package in packages:
        if platform.system() == "Windows":
            command = f"py -m pip install {package}"
        else:
            command = (
                f"python3 -m pip install {package} >/tmp/pip3-stdout 2>/tmp/pip3-stderr"
            )

        try:
            res = subprocess.run(command, shell=True, check=True)
            print(f"Package {package} install SUCCESS Returned Value: {res.returncode}")
            packages_installed.append(package)
        except subprocess.CalledProcessError as e:
            if platform.system() != "Windows":
                # Retry with --break-system-packages for environments requiring it
                fallback_command = (
                    f"python3 -m pip install {package} --break-system-packages >/tmp/pip3-stdout 2>/tmp/pip3-stderr"
                )
                try:
                    res = subprocess.run(fallback_command, shell=True, check=True)
                    print(f"Package {package} install SUCCESS (--break-system-packages) Returned Value: {res.returncode}")
                    packages_installed.append(package)
                    continue
                except subprocess.CalledProcessError:
                    pass
            print(f"Package {package} install FAILED Returned Value: {e.returncode}")
            print(f"To see errors try: {command}")
            packages_failed.append(package)

    print("\nInstalling Playwright Browsers...")
    if platform.system() == "Windows":
        pw_command = "py -m playwright install"
    else:
        pw_command = "python3 -m playwright install"

    try:
        res = subprocess.run(pw_command, shell=True, check=True)
        print(f"Playwright browsers install SUCCESS Returned Value: {res.returncode}")
    except subprocess.CalledProcessError as e:
        print(f"Playwright browsers install FAILED Returned Value: {e.returncode}")
        print(f"To see errors try: {pw_command}")

    if platform.system() == "Linux":
        print("\nChecking sudo permissions for Playwright System Dependencies...")
        can_sudo = False
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            can_sudo = True
        elif subprocess.run(["sudo", "-n", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            can_sudo = True
        else:
            sudo_pwd = os.environ.get("SUDO_PASSWORD", "")
            if sudo_pwd:
                auth_res = subprocess.run(
                    ["sudo", "-S", "-v"],
                    input=sudo_pwd + "\n",
                    text=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                can_sudo = (auth_res.returncode == 0)

        if can_sudo:
            print("Installing Playwright System Dependencies...")
            pw_deps_command = "python3 -m playwright install-deps"
            try:
                res = subprocess.run(pw_deps_command, shell=True, check=True)
                print(
                    f"Playwright system dependencies install SUCCESS Returned Value: {res.returncode}"
                )
            except subprocess.CalledProcessError as e:
                print(
                    f"Playwright system dependencies install FAILED Returned Value: {e.returncode}"
                )
                print(f"To see errors try: {pw_deps_command}")
        else:
            print("WARNING: 'sudo' password required or invalid. Skipping automatic 'playwright install-deps' to prevent hang.")
            print("If Playwright fails to launch, please run 'sudo python3 -m playwright install-deps' manually on this Linux host.")

    print("\nInstall Complete")
    print(f"Packages Installed Success: {packages_installed}\n")

    if packages_failed:
        print(f"Packages Failed  {packages_failed}")


if __name__ == "__main__":
    main()
