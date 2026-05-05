import atexit
import logging
import os
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse

logger = logging.getLogger("codebase_convert")

_temp_dirs = []


def cleanup_temp_dirs():
    for directory in list(_temp_dirs):
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
                logger.info("Cleaned up temporary folder on exit: %s", directory)
            except OSError:
                pass


atexit.register(cleanup_temp_dirs)


def _validate_github_url(repo_url: str) -> str:
    if not isinstance(repo_url, str) or not repo_url.strip():
        raise ValueError("Repository URL is required.")

    repo_url = repo_url.strip()

    if repo_url.startswith("git@github.com:"):
        return repo_url

    parsed = urlparse(repo_url)

    if parsed.scheme != "https":
        raise ValueError("Only HTTPS GitHub repository URLs are allowed.")

    if parsed.hostname != "github.com":
        raise ValueError("Only github.com repository URLs are allowed.")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise ValueError("GitHub URL must include an owner and repository name.")

    return repo_url


def clone_github_repo(repo_url: str, verbose: bool = False) -> str:
    temp_dir = tempfile.mkdtemp(prefix="github_repo_")
    _temp_dirs.append(temp_dir)

    try:
        safe_repo_url = _validate_github_url(repo_url)

        timeout_seconds = int(os.environ.get("CODEBASE_CONVERT_GIT_TIMEOUT", "120"))

        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:limit=2m",
                "--single-branch",
                safe_repo_url,
                temp_dir,
            ],
            check=True,
            timeout=timeout_seconds,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        if verbose:
            logger.info("GitHub repository cloned to: %s", temp_dir)

        return temp_dir

    except subprocess.TimeoutExpired as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if temp_dir in _temp_dirs:
            _temp_dirs.remove(temp_dir)
        raise TimeoutError("GitHub clone timed out.") from e

    except subprocess.CalledProcessError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if temp_dir in _temp_dirs:
            _temp_dirs.remove(temp_dir)

        stderr = e.stderr[-500:] if e.stderr else "Unknown git error."
        raise RuntimeError(f"GitHub clone failed: {stderr}") from e

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if temp_dir in _temp_dirs:
            _temp_dirs.remove(temp_dir)
        raise