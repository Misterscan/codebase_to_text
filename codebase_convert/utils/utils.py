import logging
from typing import Optional

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

logger = logging.getLogger('codebase_convert')

def estimate_tokens(text: str, verbose: bool = False) -> Optional[int]:
    '''Estimate token count for LLM usage using tiktoken'''
    if not HAS_TIKTOKEN:
        return None
    try:
        enc = tiktoken.get_encoding('cl100k_base')
        return len(enc.encode(text, disallowed_special=()))
    except Exception as e:
        if verbose:
            logger.warning(f'Could not estimate tokens: {e}')
        return None

