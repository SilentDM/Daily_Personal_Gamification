import io
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# Always operate on the project folder, no matter where the app was launched from
REPO = Path(__file__).resolve().parent

# Flag for Windows to prevent a black CMD window from popping up
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Never let git wait for a password prompt (it would hang the app on startup)
_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

# Installs made with Instalar.bat (from the GitHub ZIP) have no git: they update from the ZIP instead
GITHUB_REPO = "SilentDM/Daily_Personal_Gamification"
BRANCH = "main"
VERSION_FILE = ".installed_version"          # commit of the files in this folder (ZIP installs)
_SKIP = {".venv", ".git", "__pycache__"}     # never touched by a ZIP update
_UA = {"User-Agent": "DailyPersonalGamification-updater"}


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


def _pip_install():
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


def _restart():
    # execv is unreliable on Windows (breaks on paths with spaces): spawn + exit
    script = str(Path(sys.argv[0]).resolve())
    subprocess.Popen([sys.executable, script, *sys.argv[1:]], cwd=REPO)
    sys.exit(0)  # SystemExit is not an Exception, so it passes through the callers' except


# ------------------------------------------------------------------ git installs (developers)
def _git_update():
    if _git("fetch", timeout=5).returncode != 0:
        return  # offline or no remote

    # Language-independent (the old "Your branch is behind" check broke in pt-BR)
    res = _git("rev-list", "--count", "HEAD..@{u}")
    if res.returncode != 0:
        return  # no upstream configured
    if int(res.stdout.strip() or 0) == 0:
        return  # already up to date

    # --ff-only: never creates merge commits or touches conflicting local edits
    if _git("pull", "--ff-only", timeout=60).returncode != 0:
        return
    _pip_install()
    _restart()


# ------------------------------------------------------------------ ZIP installs (Instalar.bat)
def _latest_commit(timeout=5) -> str:
    """SHA of the newest commit on GitHub (one tiny API call)."""
    req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/commits/{BRANCH}",
                                 headers={**_UA, "Accept": "application/vnd.github.sha"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        sha = resp.read().decode("ascii", "ignore").strip()
    return sha if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha) else ""


def _download_zip(sha: str, timeout=60) -> bytes:
    req = urllib.request.Request(f"https://github.com/{GITHUB_REPO}/archive/{sha}.zip", headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def apply_zip(data: bytes, target: Path = None) -> bool:
    """Copies the files of a GitHub archive over `target` (adds/overwrites, never deletes; skips .venv/.git).
    Returns True when requirements.txt changed."""
    target = (target or REPO).resolve()
    req = target / "requirements.txt"
    old_req = req.read_bytes() if req.exists() else b""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        entries = [i for i in zf.infolist() if not i.is_dir()]
        if not entries:
            raise ValueError("empty archive")
        root = entries[0].filename.split("/")[0] + "/"  # GitHub wraps everything in "<repo>-<sha>/"
        for info in entries:
            if not info.filename.startswith(root):
                continue
            rel = info.filename[len(root):]
            parts = Path(rel).parts
            if not parts or parts[0] in _SKIP or "__pycache__" in parts:
                continue
            dest = (target / rel).resolve()
            if target not in dest.parents:
                continue  # never write outside the app folder
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".new")
            tmp.write_bytes(zf.read(info))
            os.replace(tmp, dest)
    new_req = req.read_bytes() if req.exists() else b""
    return new_req.replace(b"\r\n", b"\n").strip() != old_req.replace(b"\r\n", b"\n").strip()


def _zip_update():
    sha = _latest_commit()
    if not sha:
        return
    version = REPO / VERSION_FILE
    if version.exists() and version.read_text(encoding="ascii", errors="ignore").strip() == sha:
        return  # already up to date
    requirements_changed = apply_zip(_download_zip(sha))
    version.write_text(sha, encoding="ascii")
    if requirements_changed:
        _pip_install()
    _restart()


def check_for_updates():
    """Updates the app from GitHub and restarts it (git pull for developer clones, the ZIP otherwise).

    Safe by design: any problem (offline, GitHub unreachable, local changes that would conflict)
    simply lets the app start normally.
    """
    try:
        if (REPO / ".git").exists():
            _git_update()
        else:
            _zip_update()
    except Exception:
        pass
