import os
import subprocess
import sys
from pathlib import Path

# Always operate on the project folder, no matter where the app was launched from
REPO = Path(__file__).resolve().parent

# Flag for Windows to prevent a black CMD window from popping up
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Never let git wait for a password prompt (it would hang the app on startup)
_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def _git(*args, timeout=10):
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        env=_ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def check_for_updates():
    """Fetches from GitHub, fast-forwards if behind, and restarts the app.

    Safe by design: any problem (offline, not a git repo, local changes that
    would conflict, no git installed) simply lets the app start normally.
    """
    try:
        if _git("fetch", timeout=5).returncode != 0:
            return  # offline or not a git repo

        # Language-independent (the old "Your branch is behind" check broke in pt-BR)
        res = _git("rev-list", "--count", "HEAD..@{u}")
        if res.returncode != 0:
            return  # no upstream configured
        if int(res.stdout.strip() or 0) == 0:
            return  # already up to date

        # --ff-only: never creates merge commits or touches conflicting local edits
        if _git("pull", "--ff-only", timeout=60).returncode != 0:
            return

        req = REPO / "requirements.txt"
        if req.exists():
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req), "--quiet"],
                    cwd=REPO,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,
                    creationflags=CREATE_NO_WINDOW,
                )
            except Exception:
                pass  # restart anyway; the app may still work with current packages

        # execv is unreliable on Windows (breaks on paths with spaces): spawn + exit
        script = str(Path(sys.argv[0]).resolve())
        subprocess.Popen([sys.executable, script, *sys.argv[1:]], cwd=REPO)
        sys.exit(0)  # SystemExit is not an Exception, so it passes through the except below
    except Exception:
        pass