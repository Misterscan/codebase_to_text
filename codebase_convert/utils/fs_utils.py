import os
import concurrent.futures
from typing import List, Set, Callable, Tuple

def walk_filesystem_generator(path: str, should_exclude: Callable[[str, str], bool], handle_directory_exclusion: Callable, filter_directories_for_processing: Callable):
    """Single-threaded generator for file reading to avoid context-switching overhead."""
    excluded_dirs: Set[str] = set()

    for root, dirs, files in os.walk(path):
        if handle_directory_exclusion(root, path, excluded_dirs):
            continue

        # _skip_excluded_dir inline
        parent = os.path.dirname(root)
        skip = False
        while parent != path and parent != os.path.dirname(path):
            if parent in excluded_dirs:
                skip = True
                break
            parent = os.path.dirname(parent)
        if skip:
            continue

        filter_directories_for_processing(dirs, root, path)

        for file in files:
            yield (file, root, path)

def process_files_with_strategy(is_github_repo: bool, path: str, should_exclude: Callable, handle_directory_exclusion: Callable, filter_directories_for_processing: Callable, process_single_file: Callable) -> Tuple[List[str], int]:
    content_pieces = []
    processed_count = 0
    
    file_generator = walk_filesystem_generator(path, should_exclude, handle_directory_exclusion, filter_directories_for_processing)
    
    if is_github_repo:
        # Use threading for GitHub repos
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = executor.map(
                lambda f_tuple: process_single_file(f_tuple[0], f_tuple[1], f_tuple[2]),
                file_generator,
                chunksize=50
            )
            for file_result in results:
                if file_result:
                    content_pieces.append(file_result)
                    processed_count += 1
    else:
        # Single-threaded traversal for massive number of local small files
        for f_tuple in file_generator:
            file_result = process_single_file(f_tuple[0], f_tuple[1], f_tuple[2])
            if file_result:
                content_pieces.append(file_result)
                processed_count += 1
                
    return content_pieces, processed_count
