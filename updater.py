import subprocess
import sys
import os

# Flag for Windows to prevent a black CMD window from popping up
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

def check_for_updates():
    """Checks GitHub for new commits, pulls them, and restarts the app if updated."""
    try:
        # 1. Quick fetch from GitHub (3-second timeout so it never hangs if offline)
        fetch_res = subprocess.run(
            ["git", "fetch"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
            creationflags=CREATE_NO_WINDOW
        )
        if fetch_res.returncode != 0:
            return  # Not a git repo or no internet, continue normally

        # 2. Check if local branch is behind origin
        status_res = subprocess.run(
            ["git", "status", "-uno"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            creationflags=CREATE_NO_WINDOW
        )

        if "Your branch is behind" in status_res.stdout:
            # 3. Pull latest code
            pull_res = subprocess.run(
                ["git", "pull"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW
            )

            if pull_res.returncode == 0:
                # 4. Silently install any newly added requirements
                if os.path.exists("requirements.txt"):
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=CREATE_NO_WINDOW
                    )

                # 5. Restart the application with the fresh code
                os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        # If anything fails (offline, git conflict, etc.), just continue opening the app
        pass