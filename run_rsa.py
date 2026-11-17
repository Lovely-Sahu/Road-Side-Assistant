"""
One-step local start for RSA (development / demo).

    python run_rsa.py          (or double-click start_rsa.bat on Windows)

What it does, in order:
1. Works from the folder this file is in, so it always uses THIS project's rsa.db.
2. Makes sure the demo logins work (fixes only broken ones, backup first).
3. Picks a free port (5050 by default). If another copy of RSA is already
   running on that port it uses the next free one, so you never sign in to
   an old copy by mistake.
4. Opens the sign-in page, in a Chrome Incognito window when Chrome is found
   (Incognito does not autofill old saved passwords).
5. Starts the app. Press Ctrl+C to stop it.
"""

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def pick_port(preferred):
    port = preferred
    while port_in_use(port) and port < preferred + 50:
        print(f"Port {port} is already used by another program (maybe an older RSA copy). Trying {port + 1}...")
        port += 1
    return port


def chrome_path():
    if os.name != "nt":
        return None
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    return next((str(p) for p in candidates if p.exists()), None)


def open_browser_when_ready(url, health_url):
    for _ in range(60):
        try:
            urllib.request.urlopen(health_url, timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    chrome = chrome_path()
    try:
        if chrome:
            import subprocess
            subprocess.Popen([chrome, "--incognito", url])
        else:
            webbrowser.open(url)
    except Exception:
        pass


def ensure_ml_libraries():
    """The ML models need scikit-learn. Without it RSA still works, using the rule engine only."""
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        pass
    print("\nThe machine-learning models (TF-IDF + Logistic Regression / Random Forest) need scikit-learn.")
    try:
        answer = input("Install scikit-learn now? It needs internet and takes a minute. [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"
    if answer in ("", "y", "yes"):
        import subprocess
        result = subprocess.run([sys.executable, "-m", "pip", "install", "scikit-learn"])
        if result.returncode == 0:
            print("scikit-learn installed.")
            return True
    print("Continuing without ML: incident analysis uses the rules only.")
    print("To add ML later run:  python -m pip install scikit-learn")
    return False


def main():
    from reset_demo_passwords import ensure_demo_passwords

    print("=" * 66)
    print(" RSA - Roadside Assistance (local demo)")
    print("=" * 66)
    ensure_demo_passwords()
    ensure_ml_libraries()

    port = pick_port(int(os.environ.get("PORT", "5050")))
    url = f"http://127.0.0.1:{port}/login"
    print("\n" + "-" * 66)
    print(f" Open this address:  {url}")
    print(" Type the email and password by hand (passwords are case-sensitive).")
    print(" Press Ctrl+C here to stop the app.")
    print("-" * 66 + "\n")

    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_browser_when_ready, args=(url, f"http://127.0.0.1:{port}/healthz"),
                         daemon=True).start()

    os.environ["PORT"] = str(port)
    from web import app  # noqa: E402  (imports after chdir so the right rsa.db is used)

    app.run(host=os.environ.get("RSA_HOST", "127.0.0.1"), port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
