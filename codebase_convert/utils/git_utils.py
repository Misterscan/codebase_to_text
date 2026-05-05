import tempfile
import logging
import shutil
import atexit
import git
import os

logger = logging.getLogger('codebase_convert')

_temp_dirs = []

def cleanup_temp_dirs():
    for d in _temp_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                logger.info(f'Cleaned up temporary folder on exit: {d}')
            except Exception:
                pass

atexit.register(cleanup_temp_dirs)

def clone_github_repo(repo_url: str, verbose: bool = False) -> str:
    try:
        temp_dir = tempfile.mkdtemp(prefix='github_repo_')
        _temp_dirs.append(temp_dir)
        git.Repo.clone_from(repo_url, temp_dir)
        if verbose:
            logger.info(f"GitHub repository cloned to: {temp_dir}")
        return temp_dir
    except Exception as e:
        logger.error(f"Error cloning GitHub repository: {e}")
        raise
