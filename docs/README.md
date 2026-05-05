# Codebase Convert

A powerful Python tool that converts codebases (folder structures with files) into a single text file or Microsoft Word document (.docx), while preserving folder structure and file contents. Perfect for AI/LLM processing, documentation generation, and code analysis.

# Wanna see an example? This repo was converted to Markdown [here](./codebase-convert-2.0.0.md).

## ✨ Features

- **Multi-source input**: Local directories and GitHub repositories
- **Flexible output**: Text files (.txt), Markdown (.md), and Microsoft Word documents (.docx)
- **AI Optimized Output**: Formatting and compression designed explicitly for LLM contexts (enabled by default)
- **Token Estimation**: Automatically calculates rough token counts string size using `tiktoken` to ensure your prompt fits into context windows.
- **Image Support**: Automatically embeds codebase images into Word documents or Base64 encodes them for text output
- **Smart exclusions**: Automatically respects local `.gitignore` files, along with advanced pattern matching for files and directories
- **Performance optimized**: Single-threaded generator traversal for local paths avoids thread overhead; multithreading is reserved for remote GitHub I/O
- **Comprehensive logging**: Detailed verbose mode for log transparency
- **Encoding support**: Handles various file encodings gracefully

## 🚀 Installation

### Option 1: Install from GitHub Release (Recommended)

You can download the pre-built package directly from the [GitHub Releases](https://github.com/Misterscan/codebase_convert/releases) page:

1. Download the `codebase_convert-2.0.0.tar.gz` or `.whl` file from the latest release.
2. Install it using pip:
   ```bash
   pip install codebase_convert-2.0.0.tar.gz
   ```

### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/Misterscan/codebase_convert.git
cd codebase_convert

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the package
pip install -e .

```

## 📖 Usage

### Web Interface & API

You can run the web application locally to access a graphical user interface (GUI) and interactive Swagger API documentation. 

```bash
# Start the web interface
python app.py
```

* **Graphical Web UI**: Open [http://127.0.0.1:5003](http://127.0.0.1:5003) to use the beautifully styled Catppuccin web interface. Just paste your codebase path/URL, set your options, and download your converted file! Once your download completes, you'll see a new **Ask AI for a Code Review** section with pre-configured, comprehensive review prompts tailored for models like ChatGPT, Claude, Gemini, DeepSeek, Mistral, Perplexity, Grok, Meta AI, HuggingChat, and Poe.
* **Swagger API Docs**: Open [http://127.0.0.1:5003/apidocs/](http://127.0.0.1:5003/apidocs/) to view the interactive API playground.

### Command Line Interface (CLI)

#### Basic Usage

```bash
cb --input "path_or_github_url" --output "output_path" --output_type "txt"
```

#### Advanced Usage with Exclusions and Settings

```bash
# Exclude specific patterns
cb --input "./my_project" --output "output.md" --output_type "md" --exclude "*.log,temp/,**/__pycache__/**"

# Disable AI Optimization (keeps empty lines, raw formats)
cb --input "./my_project" --output "output.docx" --output_type "docx" --no_ai_optimize

# Strip Comments
cb --input "./my_project" --output "output.txt" --output_type "txt" --strip_comments

# Verbose logging output
cb --input "./my_project" --output "output.txt" --output_type "txt" --verbose
```

### Python API

```python
from codebase_convert import CodebaseConvert

# Basic usage — use as a context manager to ensure safe resource cleanup
with CodebaseConvert(
    input_path="path_or_github_url",
    output_path="output_path",
    output_type="md"
) as converter:
    converter.get_file()

# Advanced usage with exclusions and AI optimization
with CodebaseConvert(
    input_path="./my_project",
    output_path="./output.md",
    output_type="md",
    exclude=["*.log", "temp/", "**/__pycache__/**"],
    exclude_hidden=True,
    ai_optimize=True,  # Defaults to True. Set to False to retain raw whitespace formats
    strip_comments=False, # Defaults to False. Set to True to remove all prefixed comments
    verbose=True
) as converter:
    converter.get_file()

    # Get text content without saving to file
    text_content = converter.get_text()
    print(text_content)

# Token estimation (uses cl100k_base encoding via tiktoken)
from codebase_convert.utils import estimate_tokens
token_count = estimate_tokens(text_content)
print(f"Estimated tokens: {token_count:,}")
```

## 🎯 Exclusion Patterns

The tool supports powerful exclusion patterns to filter out unwanted files and directories:

### Pattern Types

1. **Exact filename**: `README.md`, `config.yaml`
2. **Wildcard patterns**: `*.log`, `*.tmp`, `test_*`
3. **Directory patterns**: `__pycache__/`, `.git/`, `node_modules/`
4. **Recursive patterns**: `**/__pycache__/**`, `**/node_modules/**`
5. **Path-based patterns**: `src/temp/`, `docs/build/`

### Exclusion Sources

1. **`.gitignore`**: The tool automatically attempts to read `.gitignore` at the root path and applies its rules.
2. **CLI Arguments**: Use `--exclude` flag (can be used multiple times)
3. **`.exclude` file**: Place in your project root (see example below)
4. **Default patterns**: Common files/folders are excluded automatically

### Default Exclusions

The tool automatically excludes common development files:

- `.git/`, `__pycache__/`, `*.pyc`, `*.pyo`
- `node_modules/`, `.venv/`, `venv/`, `env/`
- `*.log`, `*.tmp`, `.DS_Store`
- `.pytest_cache/`, `build/`, `dist/`

When `ai_optimize` is enabled (default), various media and binary files (`*.mp3`, `*.pdf`, `*.ttf`, etc.) are also automatically excluded to keep outputs clean.

## 📝 .exclude File Example

Create a `.exclude` file in your project root:

```bash
# .exclude file - Patterns for files/folders to exclude

# Version control
.git/
.gitignore

# Python
__pycache__/
*.pyc
venv/
.pytest_cache/

# Node.js
node_modules/
*.log

# IDE files
.vscode/
.idea/

# Project specific
config/secrets.yaml
data/large_files/
```

## 🔧 CLI Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--input` | Input path (local folder or GitHub URL) | `./my_project` or `https://github.com/user/repo` |
| `--output` | Output file path | `./output.txt` |
| `--output_type` | Output format (`txt` or `docx`) | `txt` |
| `--exclude` | Exclusion patterns (repeatable) | `--exclude "*.log" --exclude "temp/"` |
| `--exclude_hidden` | Exclude hidden files/folders | Flag (no value) |
| `--no_ai_optimize` | Disable AI-optimized output | Flag (no value) |
| `--strip_comments` | Strip comments from code | Flag (no value) |
| `--verbose` | Enable detailed logging | Flag (no value) |

## 💡 Examples

### Convert Local Project

```bash
# Basic conversion
cb --input "~/projects/my_app" --output "my_app_code.md" --output_type "md"

# With custom exclusions
cb --input "~/projects/my_app" --output "my_app_code.txt" --output_type "txt" --exclude "*.log,build/,dist/" --verbose
```

### Convert GitHub Repository

```bash
# Public repository
cb --input "https://github.com/username/repo" --output "repo_analysis.docx" --output_type "docx"

# With exclusions for cleaner output
cb --input "https://github.com/username/repo" --output "repo_clean.txt" --output_type "txt" --exclude "*.md,docs/,examples/"
```

### Python Integration

```python
# Analyze a codebase programmatically
from codebase_convert import CodebaseConvert

def analyze_codebase(project_path):
    with CodebaseConvert(
        input_path=project_path,
        output_path="analysis.txt",
        output_type="txt",
        exclude=["*.log", "test/", "**/__pycache__/**"],
        ai_optimize=True,
        strip_comments=False,
        verbose=True
    ) as converter:
        # Get the content
        content = converter.get_text()

    # Process with your preferred LLM/AI tool
    # analysis_result = your_ai_tool.analyze(content)
    return content

# Usage
code_content = analyze_codebase("./my_project")
```

## 🎯 Use Cases

- **AI/LLM Training**: Prepare codebases for language model training
- **Code Review**: Generate comprehensive code overviews for review
- **Documentation**: Create single-file documentation from projects
- **Analysis**: Feed entire codebases to AI tools for analysis
- **Migration**: Document legacy codebases before migration
- **Learning**: Study open-source projects more effectively

## 🏗️ Architecture

The package is structured into focused, single-responsibility services:

```
codebase_to_text/
├── app.py                          # Flask web server — REST API + form routes
├── setup.py                        # Package build configuration
├── requirements.txt                # Runtime dependencies
├── templates/
│   └── index.html                  # Catppuccin web UI
├── tests/
│   └── test_codebase_convert.py    # Full unit test suite
├── docs/
│   └── README.md                   # This file
└── codebase_convert/
    ├── __init__.py                 # Package entry point
    ├── codebase_convert.py         # Core orchestration and formatter strategy classes
    └── utils/
        ├── __init__.py             # Public re-exports for all utilities
        ├── utils.py                # Token estimation (cl100k_base via tiktoken)
        ├── git_utils.py            # GitHub clone service with atexit cleanup registry
        ├── fs_utils.py             # Filesystem walker (generator for local, threaded for remote)
        └── image_utils.py          # Image compression and type detection
```

### Key Design Decisions

**Strategy Pattern for Output Formats**
`TxtFormatter`, `MdFormatter`, and `DocxFormatter` all implement the `OutputFormatter` abstract base class. Each formatter owns its own `format_file_success()`, `format_file_error()`, `combine_text()`, and `save_file()` methods — including all `python-docx` object manipulation inside `DocxFormatter`. `get_file()` in `CodebaseConvert` simply delegates to `self.formatter.save_file(...)` with no output-type branching logic.

**Filesystem Walker Strategy**
`fs_utils.py` exposes a `walk_filesystem_generator()` that yields `(file, root, base_path)` tuples lazily. `process_files_with_strategy()` decides whether to consume that generator synchronously (local paths) or via a `ThreadPoolExecutor` (GitHub clones), keeping threading overhead off small local repositories.

**GitHub Clone Lifecycle**
`git_utils.py` maintains a module-level `_temp_dirs` registry. Every directory created by `clone_github_repo()` is appended to this list, and `atexit.register(cleanup_temp_dirs)` ensures all of them are deleted on process exit — including on `SIGTERM` — without relying on `__exit__` being called.

**Security: Path Traversal Prevention**
`_safe_input_path()` in `app.py` calls `pathlib.Path.resolve()` on both the input path and the workspace root before the `startswith` comparison, neutralising symlink-based directory escape attempts that `os.path.abspath` does not catch.

**Token Estimation**
All token counting is centralised in `codebase_convert/utils/utils.py` using `tiktoken`'s `cl100k_base` encoding. Neither `CodebaseConvert` nor `app.py` contain their own counting logic; both import from `codebase_convert.utils`.

## 🔄 Output Format

The generated output includes:

1. **Folder Structure**: Tree-like representation of the directory structure
2. **File Contents**: Full content of each file with metadata
3. **Clear Separators**: Distinct sections for easy navigation

## 🤝🏾 Contributing

Contributions are welcome! Please follow these steps:

- Fork the repository.
- Create a new branch (git checkout -b feature_branch).
- Make your changes.
- Commit your changes (git commit -am 'Add new feature').
- Push to the branch (git push origin feature_branch).
- Create a new Pull Request.

## ✒️ License

This project is licensed under the MIT License - see [LICENSE](./LICENSE.md) for details.

==================================================================

Feel free to customize this template to better suit your project's specifics. Ensure you update placeholders like `"path_or_github_url"`, `"output_path"`, `"txt"`, and `"docx"` with actual values and add any additional sections or information that you think would be useful for your users.