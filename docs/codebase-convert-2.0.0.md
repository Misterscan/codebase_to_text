# Folder Structure

```text
codebase_to_text/
    app.py
    LICENSE
    requirements.txt
    setup.cfg
    setup.py
    codebase_convert/
        codebase_convert.py
        pytest.ini
        requirements-dev.txt
        __init__.py
        utils/
            fs_utils.py
            git_utils.py
            image_utils.py
            utils.py
            __init__.py
    converted-repos/
    docs/
        codebase-convert-2.0.0.md
        README.md
    templates/
        index.html
    tests/
        test_codebase_convert.py
        __init__.py
```

# File Contents

### File: `app.py`

```python
import os
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template
from flasgger import Swagger
from codebase_convert.codebase_convert import CodebaseConvert
app = Flask(__name__)
# Configure Flasgger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}
swagger = Swagger(app, config=swagger_config, template={
    "info": {
        "title": "Codebase Convert API",
        "description": "API for converting a codebase (local path or GitHub URL) into text, markdown, or docx.",
        "version": "2.0.0"
    }
})
@app.route('/api/convert', methods=['POST'])
def convert():
    """
    Convert a codebase to a single text document
    ---
    tags:
      - Conversion
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - input
          properties:
            input:
              type: string
              description: GitHub URL or absolute local path to the codebase
              example: "https://github.com/QaisarRajput/codebase_to_text"
            output_type:
              type: string
              enum: ['txt', 'md', 'docx']
              default: 'txt'
              description: The format of the output file
            exclude:
              type: array
              items:
                type: string
              description: Patterns to exclude
              example: ["*.log", "temp/", "**/__pycache__/**"]
            exclude_hidden:
              type: boolean
              default: true
              description: Exclude hidden files and directories (like .git, .env)
            ai_optimize:
              type: boolean
              default: true
              description: Optimize the output format for AI processing (strips empty lines, removes binary files, etc.)
            strip_comments:
              type: boolean
              default: false
              description: Strip single-line comments from the code
            verbose:
              type: boolean
              default: false
              description: Enable verbose logging output (prints to stdout)
    responses:
      200:
        description: The generated document file
        content:
          application/octet-stream: {}
      400:
        description: Invalid request parameters
      500:
        description: Conversion failed
    """
    data = request.json or {}
    input_path = data.get('input')
    if not input_path:
        return jsonify({"error": "The 'input' parameter is required. It must be a valid GitHub URL or local path."}), 400
    output_type = data.get('output_type', 'txt')
    if output_type not in ['txt', 'md', 'docx']:
        return jsonify({"error": "output_type must be txt, md, or docx."}), 400
    exclude = data.get('exclude', [])
    exclude_hidden = data.get('exclude_hidden', True)
    ai_optimize = data.get('ai_optimize', True)
    strip_comments = data.get('strip_comments', False)
    verbose = data.get('verbose', False)
    return _process_conversion(input_path, output_type, exclude, exclude_hidden, ai_optimize, strip_comments, verbose, True)
def _safe_input_path(input_path: str) -> bool:
    if input_path.startswith("https://github.com/") or input_path.startswith("git@github.com:"):
        return True
    try:
        from urllib.parse import urlparse
        if urlparse(input_path).scheme in ['http', 'https']:
            return True
        WORKSPACE_DIR = Path(os.getcwd()).resolve()
        abs_path = Path(input_path).resolve()
        # Check if the resolved input path starts with the resolved workspace dir
        # We check path parts to ensure it's strictly contained
        return str(abs_path).startswith(str(WORKSPACE_DIR))
    except Exception:
        return False
def _process_conversion(input_path, output_type, exclude, exclude_hidden, ai_optimize, strip_comments, verbose, is_json, download_filename=None):
    if not _safe_input_path(input_path):
        err = "Path traversal detected or invalid path. Input must be within the designated workspace or a valid URL."
        return (jsonify({"error": err}), 403) if is_json else (err, 403)
    # Use a secure temp file to generate output 
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_type}") as temp_out:
        output_file = temp_out.name
    try:
        # Initialize converter
        with CodebaseConvert(
            input_path=input_path,
            output_path=output_file,
            output_type=output_type,
            exclude=exclude,
            exclude_hidden=exclude_hidden,
            ai_optimize=ai_optimize,
            strip_comments=strip_comments,
            verbose=verbose
        ) as converter:
            # Execute the conversion
            text_output = converter.get_text()
            converter.get_file(text_output=text_output)
            from codebase_convert.utils import estimate_tokens
            token_count = estimate_tokens(text_output, verbose=verbose) or 0
            response = send_file(
                output_file, 
                as_attachment=True, 
                download_name=download_filename or f"codebase_output.{output_type}"
            )
            response.headers['X-Token-Count'] = str(token_count)
            response.headers['Access-Control-Expose-Headers'] = 'X-Token-Count'
            return response
    except Exception as e:
        return (jsonify({"error": str(e)}), 500) if is_json else (f"Conversion failed: {str(e)}", 500)
@app.route('/', methods=['GET'])
def index():
    """
    Render the Graphical Web UI
    """
    return render_template('index.html')
@app.route('/api/form-convert', methods=['POST'])
def form_convert():
    """
    Handle form submissions from the Web UI to download the output.
    """
    input_path = request.form.get('input')
    if not input_path:
        return "The 'input' parameter is required.", 400
    output = request.form.get('output')
    if not output:
        return "The 'output' parameter is required.", 400
    output_type = request.form.get('output_type', 'txt')
    exclude_raw = request.form.get('exclude', '')
    exclude = [e.strip() for e in exclude_raw.split(',')] if exclude_raw else []
    # Checkboxes only send data if checked
    exclude_hidden = request.form.get('exclude_hidden') == 'on'
    verbose = request.form.get('verbose') == 'on'
    no_ai_optimize = request.form.get('no_ai_optimize') == 'on'
    ai_optimize = not no_ai_optimize
    strip_comments = request.form.get('strip_comments') == 'on'
    download_filename = output
    return _process_conversion(input_path, output_type, exclude, exclude_hidden, ai_optimize, strip_comments, verbose, False, download_filename)
if __name__ == '__main__':
    # Add an explicit port mapping. Runs on http://127.0.0.1:5003 by default.
    app.run(debug=True, host='0.0.0.0', port=5003)
```

### File: `LICENSE`

```
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/
   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION
   1. Definitions.
      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.
      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.
      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.
      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.
      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.
      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.
      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).
      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.
      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."
      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.
   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.
   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.
   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:
      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and
      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and
      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and
      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.
      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.
   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.
   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.
   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.
   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.
   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.
   END OF TERMS AND CONDITIONS
   APPENDIX: How to apply the Apache License to your work.
      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.
   Copyright [yyyy] [name of copyright owner]
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```

### File: `requirements.txt`

```
python-docx>=0.8.11
gitpython
Pillow
pathspec>=0.11.0
tiktoken>=0.5.0
flask
flasgger
```

### File: `setup.cfg`

```
# Inside of setup.cfg
[metadata]
description-file = README.md
```

### File: `setup.py`

```python
# Modified from Qaisar Tanvir's original codebase-convert setup.py to include Pillow for image support in python-docx and updated version numbers for dependencies.
from setuptools import setup, find_packages
import os
print(os.path.dirname(__file__))
setup(
    name="codebase_convert",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "python-docx>=0.8.11",  # Specify minimum version for image support
        "gitpython",
        "pathspec>=0.11.0",
        "tiktoken>=0.5.0",
        "Pillow",
        "flask",
        "flasgger"
    ],
    entry_points={
        "console_scripts": [
            "cb = codebase_convert.codebase_convert:main",
        ]
    },
    author="Misterscan",
    author_email="misterscanmusic@aol.com",
    description="A Python package to convert codebase to text",
    license="MIT",
    long_description=open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs/README.md"), "r", encoding="utf-8").read(),
    download_url="https://github.com/Misterscan/codebase_convert/releases/download/v2.0.0/codebase_convert-2.0.0.tar.gz",
    long_description_content_type="text/markdown",
    keywords = ["codebase, code conversion, text conversion, folder structure, file contents, text extraction, document conversion, Python package, GitHub repository, command-line tool, code analysis, file parsing, code documentation, formatting preservation, readability"],
    url="https://github.com/Misterscan/codebase_convert",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
    ],
)
```

### File: `codebase_convert\codebase_convert.py`

```python
"""
Codebase to Text Converter
This module provides functionality to convert codebases (folder structures with files)
into a single text file, markdown file (.md), or Microsoft Word document (.docx), while preserving folder
structure and file contents. It supports advanced exclusion patterns and GitHub repositories.
"""
import os
import argparse
import shutil
import fnmatch
import tempfile
import sys
import base64
import io
import logging
import uuid
import abc
from typing import List, Optional, Set, Tuple, Any
from codebase_convert.utils import clone_github_repo, process_files_with_strategy, is_image_file, compress_image
class OutputFormatter(abc.ABC):
    @abc.abstractmethod
    def format_file_success(self, file_path: str, base_path: str, file_content: str, ext: str, ai_optimize: bool) -> str:
        pass
    @abc.abstractmethod
    def format_file_error(self, file_path: str, base_path: str, error: Exception) -> str:
        pass
    @abc.abstractmethod
    def combine_text(self, folder_structure: str, file_contents: str) -> str:
        pass
    def save_file(self, text: str, output_path: str, verbose: bool) -> None:
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(text)
class TxtFormatter(OutputFormatter):
    def format_file_success(self, file_path: str, base_path: str, file_content: str, ext: str, ai_optimize: bool) -> str:
        rel_path = os.path.relpath(file_path, base_path)
        if ai_optimize:
            content = f"<file path=\"{rel_path}\">\n"
            content += f"{file_content}\n"
            content += f"\n</file>\n"
            return content
        content = f"\n\n{rel_path}\n"
        content += f"File type: {ext or 'no extension'}\n"
        content += f"{file_content}"
        content += f"\n\n{'-' * 50}\nFile End\n{'-' * 50}\n"
        return content
    def format_file_error(self, file_path: str, base_path: str, error: Exception) -> str:
        rel_path = os.path.relpath(file_path, base_path)
        content = f"\n\n{rel_path}\n"
        content += f"File type: {os.path.splitext(file_path)[1] or 'no extension'}\n"
        content += f"[Error: Could not process file - {str(error)}]"
        content += f"\n\n{'-' * 50}\nFile End\n{'-' * 50}\n"
        return content
    def combine_text(self, folder_structure: str, file_contents: str) -> str:
        folder_structure_header = "Folder Structure"
        file_contents_header = "File Contents"
        delimiter = "-" * 50
        return (f"{folder_structure_header}\n{delimiter}\n{folder_structure}\n\n"
                f"{file_contents_header}\n{delimiter}\n{file_contents}")
class DocxFormatter(TxtFormatter):
    def __init__(self):
        self.marker_start = f"(IMAGE_MARKER_{uuid.uuid4().hex})"
        self.marker_end = f"(/IMAGE_MARKER_{uuid.uuid4().hex})"
    def save_file(self, text: str, output_path: str, verbose: bool) -> None:
        doc = Document()
        segments = text.split(self.marker_start)
        if segments[0].strip():
            doc.add_paragraph(segments[0])
        for segment in segments[1:]:
            if self.marker_end in segment:
                img_path, text_content = segment.split(self.marker_end, 1)
                img_path = str(img_path.strip())
                if verbose:
                    logger.debug(f"Loading image from: {img_path}")
                if not os.path.exists(img_path):
                    if verbose:
                        logger.warning(f"Image file not found at: {img_path}")
                    doc.add_paragraph(f"[Missing image: {img_path}]")
                else:
                    try:
                        doc.add_picture(img_path, width=Inches(6))
                    except Exception as e:
                        if verbose:
                            logger.error(f"Error adding image {img_path}: {e}")
                        doc.add_paragraph(f"[Error: Could not add image - {str(e)}]")
                if text_content.strip():
                    doc.add_paragraph(text_content)
        doc.save(output_path)
class MdFormatter(OutputFormatter):
    def _get_lang_from_ext(self, ext: str) -> str:
        extension_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript', 
            '.jsx': 'jsx', '.tsx': 'tsx', '.html': 'html', '.css': 'css', 
            '.json': 'json', '.md': 'markdown', '.yml': 'yaml', '.yaml': 'yaml',
            '.sh': 'bash', '.go': 'go', '.rs': 'go', '.java': 'java', 
            '.cpp': 'java', '.c': 'c', '.h': 'c', '.cs': 'csharp', 
            '.rb': 'ruby', '.php': 'php', '.sql': 'sql', '.xml': 'xml'
        }
        return extension_map.get(ext.lower(), '')
    def format_file_success(self, file_path: str, base_path: str, file_content: str, ext: str, ai_optimize: bool) -> str:
        rel_path = os.path.relpath(file_path, base_path)
        lang = self._get_lang_from_ext(ext)
        return f"\n### File: `{rel_path}`\n\n```{lang}\n{file_content}\n```\n"
    def format_file_error(self, file_path: str, base_path: str, error: Exception) -> str:
        rel_path = os.path.relpath(file_path, base_path)
        return f"\n### File: `{rel_path}`\n\n```text\n[Error: Could not process file - {str(error)}]\n```\n"
    def combine_text(self, folder_structure: str, file_contents: str) -> str:
        folder_structure_header = "Folder Structure"
        file_contents_header = "File Contents"
        return (f"# {folder_structure_header}\n\n```text\n{folder_structure}```\n\n"
                f"# {file_contents_header}\n{file_contents}")
def get_formatter(output_type: str) -> OutputFormatter:
    if output_type == 'md':
        return MdFormatter()
    elif output_type == 'docx':
        return DocxFormatter()
    elif output_type == 'txt':
        return TxtFormatter()
    else:
        raise ValueError(f"Invalid output type: {output_type}. Supported types: txt, docx, md")
import git
import pathspec
from docx import Document
from docx.shared import Inches
try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
logger = logging.getLogger("codebase_convert")
class CodebaseConvert:
    """
    Convert codebase to text with advanced exclusion patterns.
    This class provides functionality to convert local directories or GitHub repositories
    into text or DOCX files while supporting sophisticated exclusion patterns including
    wildcards, directory patterns, and .exclude file support.
    """
    def __init__(self, input_path: str, output_path: str, output_type: str, verbose: bool = False,
                 exclude_hidden: bool = False, exclude: Optional[List[str]] = None, 
                 ai_optimize: bool = True, strip_comments: bool = False):
        """
        Initialize CodebaseConvert converter.
        Args:
            input_path: Path to local directory or GitHub repository URL
            output_path: Path for the output file
            output_type: Output format ('txt', 'md' or 'docx')
            verbose: Enable detailed logging (default: False)
            exclude_hidden: Exclude hidden files and directories (default: False)
            exclude: List of exclusion patterns (default: None)
            ai_optimize: Optimize output for AI readability and compress size (default: True)
            strip_comments: Remove lines with comment prefixes (default: False)
        """
        self.input_path = input_path
        self.output_path = output_path
        self.output_type = output_type
        self.config = {
            'verbose': verbose,
            'exclude_hidden': exclude_hidden,
            'ai_optimize': ai_optimize,
            'strip_comments': strip_comments,
        }
        # Configure logging
        if verbose:
            logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
        else:
            logging.basicConfig(level=logging.INFO, format='%(message)s')
        self.formatter = get_formatter(self.output_type)
        # Initialize exclusion patterns
        self.exclude_patterns: Set[str] = set()
        self.excluded_files_count = 0
        self.gitignore_spec: Optional[pathspec.PathSpec] = None
        # Load exclusion patterns from various sources
        self._load_exclusion_patterns(exclude)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    @property
    def verbose(self) -> bool:
        """Get verbose setting"""
        return self.config['verbose']
    @property
    def exclude_hidden(self) -> bool:
        """Get exclude_hidden setting"""
        return self.config['exclude_hidden']
    def _load_exclusion_patterns(self, exclude_args: Optional[List[str]]):
        """Load exclusion patterns from CLI args, defaults and .exclude file."""
        self._add_cli_patterns(exclude_args)
        self._add_default_patterns()
        self._add_file_patterns()
        self._load_gitignore()
        if self.verbose and self.exclude_patterns:
            logger.debug(f"Active exclusion patterns: {sorted(self.exclude_patterns)}")
    def _load_gitignore(self):
        """Load patterns from local .gitignore file if present."""
        gitignore_path = os.path.join(
            self.input_path if not self.is_github_repo() else '.',
            '.gitignore'
        )
        if not os.path.exists(gitignore_path):
            return
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                self.gitignore_spec = pathspec.PathSpec.from_lines('gitignore', f)
            if self.verbose:
                logger.debug(f"Loaded gitignore patterns from {gitignore_path}")
        except Exception as e:
            if self.verbose:
                logger.warning(f"Could not read .gitignore file: {e}")
    def _add_cli_patterns(self, exclude_args: Optional[List[str]]):
        """Add patterns provided via command line."""
        if not exclude_args:
            return
        for pattern in exclude_args:
            for p in pattern.split(','):
                p = p.strip()
                if p:
                    self.exclude_patterns.add(p)
    def _add_default_patterns(self):
        """Add default exclusion patterns for common files/folders."""
        default_excludes = {
            '.git/', '.git/**', '.github/', '.gitlab/', '.hg/', '.hg/**',
            '__pycache__/', '**/__pycache__/**',
            '*.pyc', '*.pyo', '*.pyd',
            '.venv/', 'venv/', 'env/', '.env',
            '.env.local',
            'node_modules/',
            '.DS_Store',
            '*.log', '*.tmp',
            '.pytest_cache/',
            '.coverage',
            'build/', 'dist/',
            '*.egg-info/',
            '.vscode/', '*-lock.json', '*-lock.yaml',
            '.mypy_cache/', 'server_uploads/', '*.jsonl', '.env.keys',
            '.netlify/', '.vercel/', '.aws-sam/', '.serverless/', '.azure/', '.gcloud/',
            'coverage/', 'logs/', 'debug.log', 'debug.log.*',
            '.idea/', '*.iml', '*.iws', '*.ipr',
            '.vs/', '*.sln', '*.suo', '*.vcxproj*',
            '.gradle/', 'build/', 'out/',
            '.vscode-test/',
        }
        if self.config.get('ai_optimize', False):
            media_excludes = {
                '*.mp3', '*.mp4', '*.wav', '*.avi', '*.mov', '*.flv', '*.wmv', '*.webm', '*.ogg',
                '*.pdf', '*.eot', '*.ttf', '*.woff', '*.woff2'
            }
            default_excludes.update(media_excludes)
        self.exclude_patterns.update(default_excludes)
    def _add_file_patterns(self):
        """Load patterns from a .exclude file if present."""
        exclude_file_path = os.path.join(
            self.input_path if not self.is_github_repo() else '.',
            '.exclude'
        )
        if not os.path.exists(exclude_file_path):
            return
        try:
            with open(exclude_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.exclude_patterns.add(line)
            if self.verbose:
                logger.debug(f"Loaded exclusion patterns from {exclude_file_path}")
        except (OSError, UnicodeDecodeError) as e:
            if self.verbose:
                logger.warning(f"Warning: Could not read .exclude file: {e}")
    def _normalize_path(self, file_path: str, base_path: str) -> str:
        """Normalize path for pattern matching"""
        try:
            # Get relative path from base
            rel_path = os.path.relpath(file_path, base_path)
            # Convert to forward slashes for consistent pattern matching
            return rel_path.replace(os.sep, '/')
        except ValueError:
            # If relative path can't be computed, use absolute path
            return file_path.replace(os.sep, '/')
    def _should_exclude(self, file_path: str, base_path: str) -> bool:
        """Check if file/directory should be excluded based on patterns"""
        # Handle hidden files if exclude_hidden is True
        if self.exclude_hidden and self._is_hidden_file(file_path):
            return True
        # Normalize the path for pattern matching
        normalized_path = self._normalize_path(file_path, base_path)
        filename = os.path.basename(file_path)
        # Check against gitignore if present
        if self.gitignore_spec and self.gitignore_spec.match_file(normalized_path):
            return True
        if not self.exclude_patterns:
            return False
        # Check against all exclusion patterns
        for pattern in self.exclude_patterns:
            if self._pattern_matches(pattern, normalized_path, filename):
                return True
        return False
    def _pattern_matches(self, pattern: str, normalized_path: str, filename: str) -> bool:
        """Return True if the pattern matches the given file."""
        if fnmatch.fnmatch(filename, pattern):
            return True
        if fnmatch.fnmatch(normalized_path, pattern):
            return True
        if pattern.endswith('/'):
            if self._dir_pattern_match(pattern.rstrip('/'), normalized_path):
                return True
        if '**' in pattern:
            if self._recursive_pattern_match(pattern, normalized_path):
                return True
        return False
    def _dir_pattern_match(self, dir_pattern: str, normalized_path: str) -> bool:
        """Check directory style pattern."""
        for part in normalized_path.split('/'):
            if fnmatch.fnmatch(part, dir_pattern):
                return True
        return False
    def _recursive_pattern_match(self, pattern: str, normalized_path: str) -> bool:
        """Handle patterns that include ** for recursion."""
        recursive_pattern = pattern.replace('**/', '').replace('**', '*')
        if fnmatch.fnmatch(normalized_path, recursive_pattern):
            return True
        path_parts = normalized_path.split('/')
        for i in range(len(path_parts)):
            partial_path = '/'.join(path_parts[i:])
            if fnmatch.fnmatch(partial_path, recursive_pattern):
                return True
        return False
    def _parse_folder(self, folder_path: str) -> str:
        """Parse folder structure, respecting exclusion patterns"""
        tree = ""
        excluded_dirs: Set[str] = set()
        for root, dirs, files in os.walk(folder_path):
            if self._handle_excluded_directory(root, folder_path, excluded_dirs):
                continue
            if self._skip_excluded_dir(root, excluded_dirs):
                continue
            self._filter_excluded_directories(dirs, root, folder_path)
            tree += self._generate_directory_entry(root, folder_path)
            tree += self._generate_file_entries(files, root, folder_path)
        self._log_tree_results(tree)
        return tree
    def _handle_excluded_directory(self, root: str, folder_path: str, excluded_dirs: Set[str]) -> bool:
        """Handle directory exclusion and return True if directory should be skipped"""
        if self._should_exclude(root, folder_path):
            if self.verbose:
                logger.debug(f"Excluding directory: {root}")
            self.excluded_files_count += 1
            excluded_dirs.add(root)
            return True
        return False
    def _filter_excluded_directories(self, dirs: List[str], root: str, folder_path: str):
        """Filter out excluded directories from the dirs list"""
        original_dirs = dirs[:]
        dirs[:] = []
        for d in original_dirs:
            dir_path = os.path.join(root, d)
            if not self._should_exclude(dir_path, folder_path):
                dirs.append(d)
            elif self.verbose:
                logger.debug(f"Excluding directory from tree: {dir_path}")
                self.excluded_files_count += 1
        # Apply hidden file exclusion
        if self.exclude_hidden:
            dirs[:] = [d for d in dirs if not self._is_hidden_file(os.path.join(root, d))]
    def _generate_directory_entry(self, root: str, folder_path: str) -> str:
        """Generate tree entry for a directory"""
        level = root.replace(folder_path, '').count(os.sep)
        indent = ' ' * 4 * level
        return f'{indent}{os.path.basename(root)}/\n'
    def _generate_file_entries(self, files: List[str], root: str, folder_path: str) -> str:
        """Generate tree entries for files in a directory"""
        tree = ""
        level = root.replace(folder_path, '').count(os.sep)
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            file_path = os.path.join(root, f)
            if not self._should_exclude(file_path, folder_path):
                tree += f'{subindent}{f}\n'
            elif self.verbose:
                logger.debug(f"Excluding file from tree: {file_path}")
                self.excluded_files_count += 1
        return tree
    def _log_tree_results(self, tree: str):
        """Log tree generation results if verbose mode is enabled"""
        if self.verbose:
            logger.debug(f"The file tree to be processed:\n{tree}")
            logger.debug(f"Total excluded items: {self.excluded_files_count}")
    def _get_file_contents(self, file_path: str) -> str:
        """Read file contents with better error handling"""
        try:
            # Try UTF-8 first
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            try:
                # Fall back to latin-1 for binary-like files
                with open(file_path, 'r', encoding='latin-1') as file:
                    content = file.read()
                    return f"[Binary/Non-UTF8 file - showing first 500 chars]\n{content[:500]}..."
            except OSError as e:
                return f"[Could not read file content: {str(e)}]"
        except OSError as e:
            return f"[Error reading file: {str(e)}]"
    def _is_hidden_file(self, file_path: str) -> bool:
        """Check if file/directory is hidden"""
        components = os.path.normpath(file_path).split(os.sep)
        for c in components:
            if c.startswith((".", "__")):
                return True
        return False
    def _skip_excluded_dir(self, root: str, excluded_dirs: Set[str]) -> bool:
        """Return True if the directory is inside an excluded path."""
        for excluded_dir in excluded_dirs:
            if root.startswith(excluded_dir):
                return True
        return False
    def _process_files(self, path: str) -> str:
        """Process files based on local or remote strategy, respecting exclusion patterns"""
        content_pieces, processed_count = process_files_with_strategy(
            self.is_github_repo(),
            path,
            self._should_exclude,
            self._handle_directory_exclusion,
            self._filter_directories_for_processing,
            self._process_single_file
        )
        if self.verbose:
            logger.info(f"Processed {processed_count} files")
        return "".join(content_pieces)
    def _handle_directory_exclusion(self, root: str, path: str, excluded_dirs: Set[str]) -> bool:
        """Handle directory exclusion for file processing"""
        if self._should_exclude(root, path):
            if self.verbose:
                logger.debug(f"Skipping excluded directory: {root}")
            excluded_dirs.add(root)
            return True
        return False
    def _filter_directories_for_processing(self, dirs: List[str], root: str, path: str):
        """Filter directories to avoid processing excluded ones"""
        original_dirs = dirs[:]
        dirs[:] = []
        for d in original_dirs:
            dir_path = os.path.join(root, d)
            if not self._should_exclude(dir_path, path):
                dirs.append(d)
    def _process_single_file(self, file: str, root: str, path: str) -> Optional[str]:
        """Process a single file and return its content or None if excluded"""
        file_path = os.path.join(root, file)
        if self._should_exclude(file_path, path):
            if self.verbose:
                logger.debug(f"Skipping excluded file: {file_path}")
            return None
        if self.verbose:
            logger.debug(f"Processing: {file_path}")
        try:
            if self.output_type == 'docx' and is_image_file(file_path):
                # For images in docx mode, return special marker with evaluated path
                return f"\n\n{self.formatter.marker_start}{os.path.abspath(file_path)}{self.formatter.marker_end}\n"
            if self.config.get('ai_optimize', False) and is_image_file(file_path):
                try:
                    rel_path = os.path.relpath(file_path, path)
                    # Attempt to compress the image
                    blob_bytes, mime_type = compress_image(file_path, verbose=self.verbose)
                    if blob_bytes:
                        blob = base64.b64encode(blob_bytes).decode('utf-8')
                        return f'<image path="{rel_path}" type="{mime_type}" compressed="true">\n{blob}\n</image>\n\n'
                    else:
                        # Fallback to original encoding if compression fails
                        with open(file_path, 'rb') as img_file:
                            blob = base64.b64encode(img_file.read()).decode('utf-8')
                        ext = os.path.splitext(file_path)[1].lower().replace('.', '')
                        if ext == 'jpg': ext = 'jpeg'
                        return f'<image path="{rel_path}" type="image/{ext}">\n{blob}\n</image>\n\n'
                except Exception as e:
                    return f"[Error: Could not convert image to blob - {str(e)}]\n"
            return self._format_file_content(file_path, path)
        except (OSError, UnicodeDecodeError) as e:
            return self._format_file_error(file_path, path, e)
    def _optimize_for_ai(self, content: str) -> str:
        lines = content.splitlines()
        cleaned = []
        comment_prefixes = ('//', '#', '/*', '*')
        strip_comments = self.config.get('strip_comments', False)
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if strip_comments and stripped.startswith(comment_prefixes):
                continue
            cleaned.append(line)
        return '\n'.join(cleaned)
    def _get_lang_from_ext(self, ext: str) -> str:
        extension_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript', 
            '.jsx': 'jsx', '.tsx': 'tsx', '.html': 'html', '.css': 'css', 
            '.json': 'json', '.md': 'markdown', '.yml': 'yaml', '.yaml': 'yaml',
            '.sh': 'bash', '.go': 'go', '.rs': 'go', '.java': 'java', 
            '.cpp': 'java', '.c': 'c', '.h': 'c', '.cs': 'csharp', 
            '.rb': 'ruby', '.php': 'php', '.sql': 'sql', '.xml': 'xml'
        }
        return extension_map.get(ext.lower(), '')
    def _format_file_content(self, file_path: str, base_path: str) -> str:
        """Format successful file content for output"""
        file_content = self._get_file_contents(file_path)
        ext = os.path.splitext(file_path)[1]
        if self.config.get('ai_optimize', True):
            file_content = self._optimize_for_ai(file_content)
        return self.formatter.format_file_success(file_path, base_path, file_content, ext, self.config.get('ai_optimize', True))
    def _format_file_error(self, file_path: str, base_path: str, error: Exception) -> str:
        """Format file processing error for output"""
        if self.verbose:
            logger.error(f"Error processing {file_path}: {error}")
        return self.formatter.format_file_error(file_path, base_path, error)
    def get_text(self) -> str:
        """Generate the combined text output"""
        folder_structure = ""
        file_contents = ""
        if self.is_github_repo():
            temp_folder_path = clone_github_repo(self.input_path, self.verbose)
            if temp_folder_path is None:
                raise RuntimeError("Failed to create temporary folder for GitHub repository")
            folder_structure = self._parse_folder(temp_folder_path)
            file_contents = self._process_files(temp_folder_path)
        else:
            folder_structure = self._parse_folder(self.input_path)
            file_contents = self._process_files(self.input_path)
        # Section headers
        return self.formatter.combine_text(folder_structure, file_contents)
    # Estimate token method removed. Use codebase_convert.utils.estimate_tokens instead.
    def get_file(self, text_output: Optional[str] = None):
        """Generate and save the output file"""
        if self.verbose:
            logger.info("Generating text layout...")
        text = text_output if text_output is not None else self.get_text()
        self.formatter.save_file(text, self.output_path, self.verbose)
        if self.verbose:
            logger.info(f"Output saved to: {self.output_path}")
        from codebase_convert.utils import estimate_tokens
        token_count = estimate_tokens(text, verbose=self.verbose)
        if token_count is not None:
            logger.info(f"Estimated token count (cl100k_base): ~{token_count:,}")
    #### GitHub Support ####
    def is_github_repo(self) -> bool:
        """Check if input path is a GitHub repository URL"""
        return (self.input_path.startswith("https://github.com/") or
                self.input_path.startswith("git@github.com:"))
def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Convert codebase to text with exclusion support.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input ./my_project --output output.txt --output_type txt
  %(prog)s --input https://github.com/user/repo --output repo.md --output_type md
  %(prog)s --input ./project --output out.txt --output_type txt --exclude "*.log,temp/,**/__pycache__/**"
        """
    )
    parser.add_argument("--input", help="Input path (folder or GitHub URL)", required=True)
    parser.add_argument("--output", help="Output file path", required=True)
    parser.add_argument("--output_type", help="Output file type (txt, md, or docx)",
                       choices=["txt", "docx", "md"], default="txt")
    parser.add_argument("--exclude", help="Exclude patterns (can be used multiple times)",
                       action="append", default=[])
    parser.add_argument("--exclude_hidden", help="Exclude hidden files and folders",
                       action="store_true")
    parser.add_argument("--verbose", help="Show detailed processing information",
                       action="store_true")
    parser.add_argument("--no_ai_optimize", help="Disable AI optimization (formatting, removing empty lines)",
                       action="store_true")
    parser.add_argument("--strip_comments", help="Remove comment lines from code (used with ai_optimize)",
                       action="store_true")
    args = parser.parse_args()
    try:
        with CodebaseConvert(
            input_path=args.input,
            output_path=args.output,
            output_type=args.output_type,
            verbose=args.verbose,
            exclude_hidden=args.exclude_hidden,
            exclude=args.exclude,
            ai_optimize=not args.no_ai_optimize,
            strip_comments=args.strip_comments
        ) as code_to_text:
            code_to_text.get_file()
        logger.info("✅ Conversion completed successfully!")
    except (OSError, ValueError, git.GitCommandError) as e:
        logger.error(f"❌ Error: {e}")
        return 1
    return 0
if __name__ == "__main__":
    sys.exit(main())
```

### File: `codebase_convert\pytest.ini`

```
[pytest]
testpaths = tests
addopts = -v
```

### File: `codebase_convert\requirements-dev.txt`

```
pytest
```

### File: `codebase_convert\__init__.py`

```python
# Inside of __init__.py
from codebase_convert.codebase_convert import CodebaseConvert
```

### File: `codebase_convert\utils\fs_utils.py`

```python
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
```

### File: `codebase_convert\utils\git_utils.py`

```python
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
```

### File: `codebase_convert\utils\image_utils.py`

```python
import io
import os
import logging
from typing import Tuple, Optional
logger = logging.getLogger("codebase_convert")
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico', '.webp', '.icns', '.svg'}
def is_image_file(file_path: str) -> bool:
    """Check if the file is an image based on extension"""
    return os.path.splitext(file_path)[1].lower() in IMAGE_EXTENSIONS
def compress_image(file_path: str, max_size: Tuple[int, int] = (1024, 1024), quality: int = 70, verbose: bool = False) -> Tuple[Optional[bytes], Optional[str]]:
    """Resize and compress image for smaller blob size"""
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            # Convert to RGB if necessary for JPEG compatibility
            if img.mode in ("RGBA", "P"):
                # Create a white background for transparent images
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            # Resize if larger than max_size while maintaining aspect ratio
            if img.width > max_size[0] or img.height > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            output = io.BytesIO()
            # Save as JPEG with specified quality
            img.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue(), "image/jpeg"
    except Exception as e:
        if verbose:
            logger.warning(f"Compression failed for {file_path}: {e}")
        return None, None
```

### File: `codebase_convert\utils\utils.py`

```python
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
```

### File: `codebase_convert\utils\__init__.py`

```python
from .utils import estimate_tokens
from .git_utils import clone_github_repo
from .fs_utils import process_files_with_strategy
from .image_utils import is_image_file, compress_image
__all__ = [
    'estimate_tokens',
    'clone_github_repo',
    'process_files_with_strategy',
    'is_image_file',
    'compress_image'
]
```

### File: `docs\codebase-convert-2.0.0.md`

```markdown
# Folder Structure
```text
codebase_to_text/
    app.py
    LICENSE
    requirements.txt
    setup.cfg
    setup.py
    codebase_convert/
        codebase_convert.py
        pytest.ini
        requirements-dev.txt
        __init__.py
        utils/
            fs_utils.py
            git_utils.py
            image_utils.py
            utils.py
            __init__.py
    converted-repos/
    docs/
        README.md
    templates/
        index.html
    tests/
        test_codebase_convert.py
        __init__.py
```
# File Contents
### File: `app.py`
```python
import os
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template
from flasgger import Swagger
from codebase_convert.codebase_convert import CodebaseConvert
app = Flask(__name__)
# Configure Flasgger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}
swagger = Swagger(app, config=swagger_config, template={
    "info": {
        "title": "Codebase Convert API",
        "description": "API for converting a codebase (local path or GitHub URL) into text, markdown, or docx.",
        "version": "2.0.0"
    }
})
@app.route('/api/convert', methods=['POST'])
def convert():
    """
    Convert a codebase to a single text document
    ---
    tags:
      - Conversion
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - input
          properties:
            input:
              type: string
              description: GitHub URL or absolute local path to the codebase
              example: "https://github.com/QaisarRajput/codebase_to_text"
            output_type:
              type: string
              enum: ['txt', 'md', 'docx']
              default: 'txt'
              description: The format of the output file
            exclude:
              type: array
              items:
                type: string
              description: Patterns to exclude
              example: ["*.log", "temp/", "**/__pycache__/**"]
            exclude_hidden:
              type: boolean
              default: true
              description: Exclude hidden files and directories (like .git, .env)
            ai_optimize:
              type: boolean
              default: true
              description: Optimize the output format for AI processing (strips empty lines, removes binary files, etc.)
            strip_comments:
              type: boolean
              default: false
              description: Strip single-line comments from the code
            verbose:
              type: boolean
              default: false
              description: Enable verbose logging output (prints to stdout)
    responses:
      200:
        description: The generated document file
        content:
          application/octet-stream: {}
      400:
        description: Invalid request parameters
      500:
        description: Conversion failed
    """
    data = request.json or {}
    input_path = data.get('input')
    if not input_path:
        return jsonify({"error": "The 'input' parameter is required. It must be a valid GitHub URL or local path."}), 400
    output_type = data.get('output_type', 'txt')
    if output_type not in ['txt', 'md', 'docx']:
        return jsonify({"error": "output_type must be txt, md, or docx."}), 400
    exclude = data.get('exclude', [])
    exclude_hidden = data.get('exclude_hidden', True)
    ai_optimize = data.get('ai_optimize', True)
    strip_comments = data.get('strip_comments', False)
    verbose = data.get('verbose', False)
    return _process_conversion(input_path, output_type, exclude, exclude_hidden, ai_optimize, strip_comments, verbose, True)
def _safe_input_path(input_path: str) -> bool:
    if input_path.startswith("https://github.com/") or input_path.startswith("git@github.com:"):
        return True
    try:
        from urllib.parse import urlparse
        if urlparse(input_path).scheme in ['http', 'https']:
            return True
        WORKSPACE_DIR = Path(os.getcwd()).resolve()
        abs_path = Path(input_path).resolve()
        # Check if the resolved input path starts with the resolved workspace dir
        # We check path parts to ensure it's strictly contained
        return str(abs_path).startswith(str(WORKSPACE_DIR))
    except Exception:
        return False
def _process_conversion(input_path, output_type, exclude, exclude_hidden, ai_optimize, strip_comments, verbose, is_json, download_filename=None):
    if not _safe_input_path(input_path):
        err = "Path traversal detected or invalid path. Input must be within the designated workspace or a valid URL."
        return (jsonify({"error": err}), 403) if is_json else (err, 403)
    # Use a secure temp file to generate output 
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_type}") as temp_out:
        output_file = temp_out.name
    try:
        # Initialize converter
        with CodebaseConvert(
            input_path=input_path,
            output_path=output_file,
            output_type=output_type,
            exclude=exclude,
            exclude_hidden=exclude_hidden,
            ai_optimize=ai_optimize,
            strip_comments=strip_comments,
            verbose=verbose
        ) as converter:
            # Execute the conversion
            text_output = converter.get_text()
            converter.get_file(text_output=text_output)
            from codebase_convert.utils import estimate_tokens
            token_count = estimate_tokens(text_output, verbose=verbose) or 0
            response = send_file(
                output_file, 
                as_attachment=True, 
                download_name=download_filename or f"codebase_output.{output_type}"
            )
            response.headers['X-Token-Count'] = str(token_count)
            response.headers['Access-Control-Expose-Headers'] = 'X-Token-Count'
            return response
    except Exception as e:
        return (jsonify({"error": str(e)}), 500) if is_json else (f"Conversion failed: {str(e)}", 500)
@app.route('/', methods=['GET'])
def index():
    """
    Render the Graphical Web UI
    """
    return render_template('index.html')
@app.route('/api/form-convert', methods=['POST'])
def form_convert():
    """
    Handle form submissions from the Web UI to download the output.
    """
    input_path = request.form.get('input')
    if not input_path:
        return "The 'input' parameter is required.", 400
    output = request.form.get('output')
    if not output:
        return "The 'output' parameter is required.", 400
    output_type = request.form.get('output_type', 'txt')
    exclude_raw = request.form.get('exclude', '')
    exclude = [e.strip() for e in exclude_raw.split(',')] if exclude_raw else []
    # Checkboxes only send data if checked
    exclude_hidden = request.form.get('exclude_hidden') == 'on'
    verbose = request.form.get('verbose') == 'on'
    no_ai_optimize = request.form.get('no_ai_optimize') == 'on'
    ai_optimize = not no_ai_optimize
    strip_comments = request.form.get('strip_comments') == 'on'
    download_filename = output
    return _process_conversion(input_path, output_type, exclude, exclude_hidden, ai_optimize, strip_comments, verbose, False, download_filename)
if __name__ == '__main__':
    # Add an explicit port mapping. Runs on http://127.0.0.1:5003 by default.
    app.run(debug=True, host='0.0.0.0', port=5003)
```
### File: `LICENSE`
```
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/
   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION
   1. Definitions.
      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.
      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.
      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.
      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.
      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.
      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.
      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).
      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.
      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."
      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.
   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.
   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.
   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:
      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and
      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and
      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and
      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.
      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.
   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.
   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.
   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.
   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.
   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.
   END OF TERMS AND CONDITIONS
   APPENDIX: How to apply the Apache License to your work.
      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.
   Copyright [yyyy] [name of copyright owner]
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
### File: `requirements.txt`
```
python-docx>=0.8.11
gitpython
Pillow
pathspec>=0.11.0
tiktoken>=0.5.0
flask
flasgger
```
### File: `setup.cfg`
```
# Inside of setup.cfg
[metadata]
description-file = README.md
```
### File: `setup.py`
```python
# Modified from Qaisar Tanvir's original codebase-convert setup.py to include Pillow for image support in python-docx and updated version numbers for dependencies.
from setuptools import setup, find_packages
import os
print(os.path.dirname(__file__))
setup(
    name="codebase_convert",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "python-docx>=0.8.11",  # Specify minimum version for image support
        "gitpython",
        "pathspec>=0.11.0",
        "tiktoken>=0.5.0",
        "Pillow",
        "flask",
        "flasgger"
    ],
    entry_points={
        "console_scripts": [
            "cb = codebase_convert.codebase_convert:main",
        ]
    },
    author="Misterscan",
    author_email="misterscanmusic@aol.com",
    description="A Python package to convert codebase to text",
    license="MIT",
    long_description=open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs/README.md"), "r", encoding="utf-8").read(),
    download_url="https://github.com/Misterscan/codebase_convert/releases/download/v2.0.0/codebase_convert-2.0.0.tar.gz",
    long_description_content_type="text/markdown",
    keywords = ["codebase, code conversion, text conversion, folder structure, file contents, text extraction, document conversion, Python package, GitHub repository, command-line tool, code analysis, file parsing, code documentation, formatting preservation, readability"],
    url="https://github.com/Misterscan/codebase_convert",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
    ],
)
```
### File: `codebase_convert\codebase_convert.py`
```python
"""
Codebase to Text Converter
This module provides functionality to convert codebases (folder structures with files)
into a single text file, markdown file (.md), or Microsoft Word document (.docx), while preserving folder
structure and file contents. It supports advanced exclusion patterns and GitHub repositories.
"""
import os
import argparse
import shutil
import fnmatch
import tempfile
import sys
import base64
import io
import logging
import uuid
import abc
from typing import List, Optional, Set, Tuple, Any
from codebase_convert.utils import clone_github_repo, process_files_with_strategy, is_image_file, compress_image
class OutputFormatter(abc.ABC):
    @abc.abstractmethod
    def format_file_success(self, file_path: str, base_path: str, file_content: str, ext: str, ai_optimize: bool) -> str:
        pass
    @abc.abstractmethod
    def format_file_error(self, file_path: str, base_path: str, error: Exception) -> str:
        pass
    @abc.abstractmethod
    def combine_text(self, folder_structure: str, file_contents: str) -> str:
        pass
    def save_file(self, text: str, output_path: str, verbose: bool) -> None:
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(text)
class TxtFormatter(OutputFormatter):
    def format_file_success(self, file_path: str, base_path: str, file_content: str, ext: str, ai_optimize: bool) -> str:
        rel_path = os.path.relpath(file_path, base_path)
        if ai_optimize:
            content = f"<file path=\"{rel_path}\">\n"
            content += f"{file_content}\n"
            content += f"\n</file>\n"
            return content
        content = f"\n\n{rel_path}\n"
        content += f"File type: {ext or 'no extension'}\n"
        content += f"{file_content}"
        content += f"\n\n{'-' * 50}\nFile End\n{'-' * 50}\n"
        return content
    def format_file_error(self, file_path: str, base_path: str, error: Exception) -> str:
        rel_path = os.path.relpath(file_path, base_path)
        content = f"\n\n{rel_path}\n"
        content += f"File type: {os.path.splitext(file_path)[1] or 'no extension'}\n"
        content += f"[Error: Could not process file - {str(error)}]"
        content += f"\n\n{'-' * 50}\nFile End\n{'-' * 50}\n"
        return content
    def combine_text(self, folder_structure: str, file_contents: str) -> str:
        folder_structure_header = "Folder Structure"
        file_contents_header = "File Contents"
        delimiter = "-" * 50
        return (f"{folder_structure_header}\n{delimiter}\n{folder_structure}\n\n"
                f"{file_contents_header}\n{delimiter}\n{file_contents}")
class DocxFormatter(TxtFormatter):
    def __init__(self):
        self.marker_start = f"(IMAGE_MARKER_{uuid.uuid4().hex})"
        self.marker_end = f"(/IMAGE_MARKER_{uuid.uuid4().hex})"
    def save_file(self, text: str, output_path: str, verbose: bool) -> None:
        doc = Document()
        segments = text.split(self.marker_start)
        if segments[0].strip():
            doc.add_paragraph(segments[0])
        for segment in segments[1:]:
            if self.marker_end in segment:
                img_path, text_content = segment.split(self.marker_end, 1)
                img_path = str(img_path.strip())
                if verbose:
                    logger.debug(f"Loading image from: {img_path}")
                if not os.path.exists(img_path):
                    if verbose:
                        logger.warning(f"Image file not found at: {img_path}")
                    doc.add_paragraph(f"[Missing image: {img_path}]")
                else:
                    try:
                        doc.add_picture(img_path, width=Inches(6))
                    except Exception as e:
                        if verbose:
                            logger.error(f"Error adding image {img_path}: {e}")
                        doc.add_paragraph(f"[Error: Could not add image - {str(e)}]")
                if text_content.strip():
                    doc.add_paragraph(text_content)
        doc.save(output_path)
class MdFormatter(OutputFormatter):
    def _get_lang_from_ext(self, ext: str) -> str:
        extension_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript', 
            '.jsx': 'jsx', '.tsx': 'tsx', '.html': 'html', '.css': 'css', 
            '.json': 'json', '.md': 'markdown', '.yml': 'yaml', '.yaml': 'yaml',
            '.sh': 'bash', '.go': 'go', '.rs': 'go', '.java': 'java', 
            '.cpp': 'java', '.c': 'c', '.h': 'c', '.cs': 'csharp', 
            '.rb': 'ruby', '.php': 'php', '.sql': 'sql', '.xml': 'xml'
        }
        return extension_map.get(ext.lower(), '')
    def format_file_success(self, file_path: str, base_path: str, file_content: str, ext: str, ai_optimize: bool) -> str:
        rel_path = os.path.relpath(file_path, base_path)
        lang = self._get_lang_from_ext(ext)
        return f"\n### File: `{rel_path}`\n\n```{lang}\n{file_content}\n```\n"
    def format_file_error(self, file_path: str, base_path: str, error: Exception) -> str:
        rel_path = os.path.relpath(file_path, base_path)
        return f"\n### File: `{rel_path}`\n\n```text\n[Error: Could not process file - {str(error)}]\n```\n"
    def combine_text(self, folder_structure: str, file_contents: str) -> str:
        folder_structure_header = "Folder Structure"
        file_contents_header = "File Contents"
        return (f"# {folder_structure_header}\n\n```text\n{folder_structure}```\n\n"
                f"# {file_contents_header}\n{file_contents}")
def get_formatter(output_type: str) -> OutputFormatter:
    if output_type == 'md':
        return MdFormatter()
    elif output_type == 'docx':
        return DocxFormatter()
    elif output_type == 'txt':
        return TxtFormatter()
    else:
        raise ValueError(f"Invalid output type: {output_type}. Supported types: txt, docx, md")
import git
import pathspec
from docx import Document
from docx.shared import Inches
try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
logger = logging.getLogger("codebase_convert")
class CodebaseConvert:
    """
    Convert codebase to text with advanced exclusion patterns.
    This class provides functionality to convert local directories or GitHub repositories
    into text or DOCX files while supporting sophisticated exclusion patterns including
    wildcards, directory patterns, and .exclude file support.
    """
    def __init__(self, input_path: str, output_path: str, output_type: str, verbose: bool = False,
                 exclude_hidden: bool = False, exclude: Optional[List[str]] = None, 
                 ai_optimize: bool = True, strip_comments: bool = False):
        """
        Initialize CodebaseConvert converter.
        Args:
            input_path: Path to local directory or GitHub repository URL
            output_path: Path for the output file
            output_type: Output format ('txt', 'md' or 'docx')
            verbose: Enable detailed logging (default: False)
            exclude_hidden: Exclude hidden files and directories (default: False)
            exclude: List of exclusion patterns (default: None)
            ai_optimize: Optimize output for AI readability and compress size (default: True)
            strip_comments: Remove lines with comment prefixes (default: False)
        """
        self.input_path = input_path
        self.output_path = output_path
        self.output_type = output_type
        self.config = {
            'verbose': verbose,
            'exclude_hidden': exclude_hidden,
            'ai_optimize': ai_optimize,
            'strip_comments': strip_comments,
        }
        # Configure logging
        if verbose:
            logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
        else:
            logging.basicConfig(level=logging.INFO, format='%(message)s')
        self.formatter = get_formatter(self.output_type)
        # Initialize exclusion patterns
        self.exclude_patterns: Set[str] = set()
        self.excluded_files_count = 0
        self.gitignore_spec: Optional[pathspec.PathSpec] = None
        # Load exclusion patterns from various sources
        self._load_exclusion_patterns(exclude)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    @property
    def verbose(self) -> bool:
        """Get verbose setting"""
        return self.config['verbose']
    @property
    def exclude_hidden(self) -> bool:
        """Get exclude_hidden setting"""
        return self.config['exclude_hidden']
    def _load_exclusion_patterns(self, exclude_args: Optional[List[str]]):
        """Load exclusion patterns from CLI args, defaults and .exclude file."""
        self._add_cli_patterns(exclude_args)
        self._add_default_patterns()
        self._add_file_patterns()
        self._load_gitignore()
        if self.verbose and self.exclude_patterns:
            logger.debug(f"Active exclusion patterns: {sorted(self.exclude_patterns)}")
    def _load_gitignore(self):
        """Load patterns from local .gitignore file if present."""
        gitignore_path = os.path.join(
            self.input_path if not self.is_github_repo() else '.',
            '.gitignore'
        )
        if not os.path.exists(gitignore_path):
            return
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                self.gitignore_spec = pathspec.PathSpec.from_lines('gitignore', f)
            if self.verbose:
                logger.debug(f"Loaded gitignore patterns from {gitignore_path}")
        except Exception as e:
            if self.verbose:
                logger.warning(f"Could not read .gitignore file: {e}")
    def _add_cli_patterns(self, exclude_args: Optional[List[str]]):
        """Add patterns provided via command line."""
        if not exclude_args:
            return
        for pattern in exclude_args:
            for p in pattern.split(','):
                p = p.strip()
                if p:
                    self.exclude_patterns.add(p)
    def _add_default_patterns(self):
        """Add default exclusion patterns for common files/folders."""
        default_excludes = {
            '.git/', '.git/**', '.github/', '.gitlab/', '.hg/', '.hg/**',
            '__pycache__/', '**/__pycache__/**',
            '*.pyc', '*.pyo', '*.pyd',
            '.venv/', 'venv/', 'env/', '.env',
            '.env.local',
            'node_modules/',
            '.DS_Store',
            '*.log', '*.tmp',
            '.pytest_cache/',
            '.coverage',
            'build/', 'dist/',
            '*.egg-info/',
            '.vscode/', '*-lock.json', '*-lock.yaml',
            '.mypy_cache/', 'server_uploads/', '*.jsonl', '.env.keys',
            '.netlify/', '.vercel/', '.aws-sam/', '.serverless/', '.azure/', '.gcloud/',
            'coverage/', 'logs/', 'debug.log', 'debug.log.*',
            '.idea/', '*.iml', '*.iws', '*.ipr',
            '.vs/', '*.sln', '*.suo', '*.vcxproj*',
            '.gradle/', 'build/', 'out/',
            '.vscode-test/',
        }
        if self.config.get('ai_optimize', False):
            media_excludes = {
                '*.mp3', '*.mp4', '*.wav', '*.avi', '*.mov', '*.flv', '*.wmv', '*.webm', '*.ogg',
                '*.pdf', '*.eot', '*.ttf', '*.woff', '*.woff2'
            }
            default_excludes.update(media_excludes)
        self.exclude_patterns.update(default_excludes)
    def _add_file_patterns(self):
        """Load patterns from a .exclude file if present."""
        exclude_file_path = os.path.join(
            self.input_path if not self.is_github_repo() else '.',
            '.exclude'
        )
        if not os.path.exists(exclude_file_path):
            return
        try:
            with open(exclude_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.exclude_patterns.add(line)
            if self.verbose:
                logger.debug(f"Loaded exclusion patterns from {exclude_file_path}")
        except (OSError, UnicodeDecodeError) as e:
            if self.verbose:
                logger.warning(f"Warning: Could not read .exclude file: {e}")
    def _normalize_path(self, file_path: str, base_path: str) -> str:
        """Normalize path for pattern matching"""
        try:
            # Get relative path from base
            rel_path = os.path.relpath(file_path, base_path)
            # Convert to forward slashes for consistent pattern matching
            return rel_path.replace(os.sep, '/')
        except ValueError:
            # If relative path can't be computed, use absolute path
            return file_path.replace(os.sep, '/')
    def _should_exclude(self, file_path: str, base_path: str) -> bool:
        """Check if file/directory should be excluded based on patterns"""
        # Handle hidden files if exclude_hidden is True
        if self.exclude_hidden and self._is_hidden_file(file_path):
            return True
        # Normalize the path for pattern matching
        normalized_path = self._normalize_path(file_path, base_path)
        filename = os.path.basename(file_path)
        # Check against gitignore if present
        if self.gitignore_spec and self.gitignore_spec.match_file(normalized_path):
            return True
        if not self.exclude_patterns:
            return False
        # Check against all exclusion patterns
        for pattern in self.exclude_patterns:
            if self._pattern_matches(pattern, normalized_path, filename):
                return True
        return False
    def _pattern_matches(self, pattern: str, normalized_path: str, filename: str) -> bool:
        """Return True if the pattern matches the given file."""
        if fnmatch.fnmatch(filename, pattern):
            return True
        if fnmatch.fnmatch(normalized_path, pattern):
            return True
        if pattern.endswith('/'):
            if self._dir_pattern_match(pattern.rstrip('/'), normalized_path):
                return True
        if '**' in pattern:
            if self._recursive_pattern_match(pattern, normalized_path):
                return True
        return False
    def _dir_pattern_match(self, dir_pattern: str, normalized_path: str) -> bool:
        """Check directory style pattern."""
        for part in normalized_path.split('/'):
            if fnmatch.fnmatch(part, dir_pattern):
                return True
        return False
    def _recursive_pattern_match(self, pattern: str, normalized_path: str) -> bool:
        """Handle patterns that include ** for recursion."""
        recursive_pattern = pattern.replace('**/', '').replace('**', '*')
        if fnmatch.fnmatch(normalized_path, recursive_pattern):
            return True
        path_parts = normalized_path.split('/')
        for i in range(len(path_parts)):
            partial_path = '/'.join(path_parts[i:])
            if fnmatch.fnmatch(partial_path, recursive_pattern):
                return True
        return False
    def _parse_folder(self, folder_path: str) -> str:
        """Parse folder structure, respecting exclusion patterns"""
        tree = ""
        excluded_dirs: Set[str] = set()
        for root, dirs, files in os.walk(folder_path):
            if self._handle_excluded_directory(root, folder_path, excluded_dirs):
                continue
            if self._skip_excluded_dir(root, excluded_dirs):
                continue
            self._filter_excluded_directories(dirs, root, folder_path)
            tree += self._generate_directory_entry(root, folder_path)
            tree += self._generate_file_entries(files, root, folder_path)
        self._log_tree_results(tree)
        return tree
    def _handle_excluded_directory(self, root: str, folder_path: str, excluded_dirs: Set[str]) -> bool:
        """Handle directory exclusion and return True if directory should be skipped"""
        if self._should_exclude(root, folder_path):
            if self.verbose:
                logger.debug(f"Excluding directory: {root}")
            self.excluded_files_count += 1
            excluded_dirs.add(root)
            return True
        return False
    def _filter_excluded_directories(self, dirs: List[str], root: str, folder_path: str):
        """Filter out excluded directories from the dirs list"""
        original_dirs = dirs[:]
        dirs[:] = []
        for d in original_dirs:
            dir_path = os.path.join(root, d)
            if not self._should_exclude(dir_path, folder_path):
                dirs.append(d)
            elif self.verbose:
                logger.debug(f"Excluding directory from tree: {dir_path}")
                self.excluded_files_count += 1
        # Apply hidden file exclusion
        if self.exclude_hidden:
            dirs[:] = [d for d in dirs if not self._is_hidden_file(os.path.join(root, d))]
    def _generate_directory_entry(self, root: str, folder_path: str) -> str:
        """Generate tree entry for a directory"""
        level = root.replace(folder_path, '').count(os.sep)
        indent = ' ' * 4 * level
        return f'{indent}{os.path.basename(root)}/\n'
    def _generate_file_entries(self, files: List[str], root: str, folder_path: str) -> str:
        """Generate tree entries for files in a directory"""
        tree = ""
        level = root.replace(folder_path, '').count(os.sep)
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            file_path = os.path.join(root, f)
            if not self._should_exclude(file_path, folder_path):
                tree += f'{subindent}{f}\n'
            elif self.verbose:
                logger.debug(f"Excluding file from tree: {file_path}")
                self.excluded_files_count += 1
        return tree
    def _log_tree_results(self, tree: str):
        """Log tree generation results if verbose mode is enabled"""
        if self.verbose:
            logger.debug(f"The file tree to be processed:\n{tree}")
            logger.debug(f"Total excluded items: {self.excluded_files_count}")
    def _get_file_contents(self, file_path: str) -> str:
        """Read file contents with better error handling"""
        try:
            # Try UTF-8 first
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            try:
                # Fall back to latin-1 for binary-like files
                with open(file_path, 'r', encoding='latin-1') as file:
                    content = file.read()
                    return f"[Binary/Non-UTF8 file - showing first 500 chars]\n{content[:500]}..."
            except OSError as e:
                return f"[Could not read file content: {str(e)}]"
        except OSError as e:
            return f"[Error reading file: {str(e)}]"
    def _is_hidden_file(self, file_path: str) -> bool:
        """Check if file/directory is hidden"""
        components = os.path.normpath(file_path).split(os.sep)
        for c in components:
            if c.startswith((".", "__")):
                return True
        return False
    def _skip_excluded_dir(self, root: str, excluded_dirs: Set[str]) -> bool:
        """Return True if the directory is inside an excluded path."""
        for excluded_dir in excluded_dirs:
            if root.startswith(excluded_dir):
                return True
        return False
    def _process_files(self, path: str) -> str:
        """Process files based on local or remote strategy, respecting exclusion patterns"""
        content_pieces, processed_count = process_files_with_strategy(
            self.is_github_repo(),
            path,
            self._should_exclude,
            self._handle_directory_exclusion,
            self._filter_directories_for_processing,
            self._process_single_file
        )
        if self.verbose:
            logger.info(f"Processed {processed_count} files")
        return "".join(content_pieces)
    def _handle_directory_exclusion(self, root: str, path: str, excluded_dirs: Set[str]) -> bool:
        """Handle directory exclusion for file processing"""
        if self._should_exclude(root, path):
            if self.verbose:
                logger.debug(f"Skipping excluded directory: {root}")
            excluded_dirs.add(root)
            return True
        return False
    def _filter_directories_for_processing(self, dirs: List[str], root: str, path: str):
        """Filter directories to avoid processing excluded ones"""
        original_dirs = dirs[:]
        dirs[:] = []
        for d in original_dirs:
            dir_path = os.path.join(root, d)
            if not self._should_exclude(dir_path, path):
                dirs.append(d)
    def _process_single_file(self, file: str, root: str, path: str) -> Optional[str]:
        """Process a single file and return its content or None if excluded"""
        file_path = os.path.join(root, file)
        if self._should_exclude(file_path, path):
            if self.verbose:
                logger.debug(f"Skipping excluded file: {file_path}")
            return None
        if self.verbose:
            logger.debug(f"Processing: {file_path}")
        try:
            if self.output_type == 'docx' and is_image_file(file_path):
                # For images in docx mode, return special marker with evaluated path
                return f"\n\n{self.formatter.marker_start}{os.path.abspath(file_path)}{self.formatter.marker_end}\n"
            if self.config.get('ai_optimize', False) and is_image_file(file_path):
                try:
                    rel_path = os.path.relpath(file_path, path)
                    # Attempt to compress the image
                    blob_bytes, mime_type = compress_image(file_path, verbose=self.verbose)
                    if blob_bytes:
                        blob = base64.b64encode(blob_bytes).decode('utf-8')
                        return f'<image path="{rel_path}" type="{mime_type}" compressed="true">\n{blob}\n</image>\n\n'
                    else:
                        # Fallback to original encoding if compression fails
                        with open(file_path, 'rb') as img_file:
                            blob = base64.b64encode(img_file.read()).decode('utf-8')
                        ext = os.path.splitext(file_path)[1].lower().replace('.', '')
                        if ext == 'jpg': ext = 'jpeg'
                        return f'<image path="{rel_path}" type="image/{ext}">\n{blob}\n</image>\n\n'
                except Exception as e:
                    return f"[Error: Could not convert image to blob - {str(e)}]\n"
            return self._format_file_content(file_path, path)
        except (OSError, UnicodeDecodeError) as e:
            return self._format_file_error(file_path, path, e)
    def _optimize_for_ai(self, content: str) -> str:
        lines = content.splitlines()
        cleaned = []
        comment_prefixes = ('//', '#', '/*', '*')
        strip_comments = self.config.get('strip_comments', False)
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if strip_comments and stripped.startswith(comment_prefixes):
                continue
            cleaned.append(line)
        return '\n'.join(cleaned)
    def _get_lang_from_ext(self, ext: str) -> str:
        extension_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript', 
            '.jsx': 'jsx', '.tsx': 'tsx', '.html': 'html', '.css': 'css', 
            '.json': 'json', '.md': 'markdown', '.yml': 'yaml', '.yaml': 'yaml',
            '.sh': 'bash', '.go': 'go', '.rs': 'go', '.java': 'java', 
            '.cpp': 'java', '.c': 'c', '.h': 'c', '.cs': 'csharp', 
            '.rb': 'ruby', '.php': 'php', '.sql': 'sql', '.xml': 'xml'
        }
        return extension_map.get(ext.lower(), '')
    def _format_file_content(self, file_path: str, base_path: str) -> str:
        """Format successful file content for output"""
        file_content = self._get_file_contents(file_path)
        ext = os.path.splitext(file_path)[1]
        if self.config.get('ai_optimize', True):
            file_content = self._optimize_for_ai(file_content)
        return self.formatter.format_file_success(file_path, base_path, file_content, ext, self.config.get('ai_optimize', True))
    def _format_file_error(self, file_path: str, base_path: str, error: Exception) -> str:
        """Format file processing error for output"""
        if self.verbose:
            logger.error(f"Error processing {file_path}: {error}")
        return self.formatter.format_file_error(file_path, base_path, error)
    def get_text(self) -> str:
        """Generate the combined text output"""
        folder_structure = ""
        file_contents = ""
        if self.is_github_repo():
            temp_folder_path = clone_github_repo(self.input_path, self.verbose)
            if temp_folder_path is None:
                raise RuntimeError("Failed to create temporary folder for GitHub repository")
            folder_structure = self._parse_folder(temp_folder_path)
            file_contents = self._process_files(temp_folder_path)
        else:
            folder_structure = self._parse_folder(self.input_path)
            file_contents = self._process_files(self.input_path)
        # Section headers
        return self.formatter.combine_text(folder_structure, file_contents)
    # Estimate token method removed. Use codebase_convert.utils.estimate_tokens instead.
    def get_file(self, text_output: Optional[str] = None):
        """Generate and save the output file"""
        if self.verbose:
            logger.info("Generating text layout...")
        text = text_output if text_output is not None else self.get_text()
        self.formatter.save_file(text, self.output_path, self.verbose)
        if self.verbose:
            logger.info(f"Output saved to: {self.output_path}")
        from codebase_convert.utils import estimate_tokens
        token_count = estimate_tokens(text, verbose=self.verbose)
        if token_count is not None:
            logger.info(f"Estimated token count (cl100k_base): ~{token_count:,}")
    #### GitHub Support ####
    def is_github_repo(self) -> bool:
        """Check if input path is a GitHub repository URL"""
        return (self.input_path.startswith("https://github.com/") or
                self.input_path.startswith("git@github.com:"))
def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Convert codebase to text with exclusion support.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input ./my_project --output output.txt --output_type txt
  %(prog)s --input https://github.com/user/repo --output repo.md --output_type md
  %(prog)s --input ./project --output out.txt --output_type txt --exclude "*.log,temp/,**/__pycache__/**"
        """
    )
    parser.add_argument("--input", help="Input path (folder or GitHub URL)", required=True)
    parser.add_argument("--output", help="Output file path", required=True)
    parser.add_argument("--output_type", help="Output file type (txt, md, or docx)",
                       choices=["txt", "docx", "md"], default="txt")
    parser.add_argument("--exclude", help="Exclude patterns (can be used multiple times)",
                       action="append", default=[])
    parser.add_argument("--exclude_hidden", help="Exclude hidden files and folders",
                       action="store_true")
    parser.add_argument("--verbose", help="Show detailed processing information",
                       action="store_true")
    parser.add_argument("--no_ai_optimize", help="Disable AI optimization (formatting, removing empty lines)",
                       action="store_true")
    parser.add_argument("--strip_comments", help="Remove comment lines from code (used with ai_optimize)",
                       action="store_true")
    args = parser.parse_args()
    try:
        with CodebaseConvert(
            input_path=args.input,
            output_path=args.output,
            output_type=args.output_type,
            verbose=args.verbose,
            exclude_hidden=args.exclude_hidden,
            exclude=args.exclude,
            ai_optimize=not args.no_ai_optimize,
            strip_comments=args.strip_comments
        ) as code_to_text:
            code_to_text.get_file()
        logger.info("✅ Conversion completed successfully!")
    except (OSError, ValueError, git.GitCommandError) as e:
        logger.error(f"❌ Error: {e}")
        return 1
    return 0
if __name__ == "__main__":
    sys.exit(main())
```
### File: `codebase_convert\pytest.ini`
```
[pytest]
testpaths = tests
addopts = -v
```
### File: `codebase_convert\requirements-dev.txt`
```
pytest
```
### File: `codebase_convert\__init__.py`
```python
# Inside of __init__.py
from codebase_convert.codebase_convert import CodebaseConvert
```
### File: `codebase_convert\utils\fs_utils.py`
```python
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
```
### File: `codebase_convert\utils\git_utils.py`
```python
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
```
### File: `codebase_convert\utils\image_utils.py`
```python
import io
import os
import logging
from typing import Tuple, Optional
logger = logging.getLogger("codebase_convert")
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico', '.webp', '.icns', '.svg'}
def is_image_file(file_path: str) -> bool:
    """Check if the file is an image based on extension"""
    return os.path.splitext(file_path)[1].lower() in IMAGE_EXTENSIONS
def compress_image(file_path: str, max_size: Tuple[int, int] = (1024, 1024), quality: int = 70, verbose: bool = False) -> Tuple[Optional[bytes], Optional[str]]:
    """Resize and compress image for smaller blob size"""
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            # Convert to RGB if necessary for JPEG compatibility
            if img.mode in ("RGBA", "P"):
                # Create a white background for transparent images
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            # Resize if larger than max_size while maintaining aspect ratio
            if img.width > max_size[0] or img.height > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            output = io.BytesIO()
            # Save as JPEG with specified quality
            img.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue(), "image/jpeg"
    except Exception as e:
        if verbose:
            logger.warning(f"Compression failed for {file_path}: {e}")
        return None, None
```
### File: `codebase_convert\utils\utils.py`
```python
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
```
### File: `codebase_convert\utils\__init__.py`
```python
from .utils import estimate_tokens
from .git_utils import clone_github_repo
from .fs_utils import process_files_with_strategy
from .image_utils import is_image_file, compress_image
__all__ = [
    'estimate_tokens',
    'clone_github_repo',
    'process_files_with_strategy',
    'is_image_file',
    'compress_image'
]
```
### File: `docs\README.md`
```markdown
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
```
### File: `templates\index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codebase Convert</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {
            /* Catppuccin Mocha Palette */
            --ctp-base: #1e1e2e;
            --ctp-mantle: #181825;
            --ctp-crust: #11111b;
            --ctp-text: #cdd6f4;
            --ctp-subtext1: #bac2de;
            --ctp-subtext0: #a6adc8;
            --ctp-overlay2: #9399b2;
            --ctp-overlay1: #7f849c;
            --ctp-surface2: #585b70;
            --ctp-surface1: #45475a;
            --ctp-surface0: #313244;
            --ctp-lavender: #b4befe;
            --ctp-blue: #89b4fa;
            --ctp-rosewater: #f5e0dc;
        }
        body { 
            padding: 40px; 
            background-color: var(--ctp-base); 
            color: var(--ctp-text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        h1, h2, h3, h4, h5, h6, p, .form-label, .form-check-label {
            color: var(--ctp-text) !important;
        }
        .card { 
            max-width: 800px; 
            margin: 0 auto; 
            background-color: var(--ctp-mantle);
            border: 1px solid var(--ctp-surface0);
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border-radius: 12px;
        }
        .text-muted { color: var(--ctp-overlay1) !important; }
        /* Form Inputs */
        .form-control, .form-select {
            background-color: var(--ctp-surface0);
            border: 1px solid var(--ctp-surface1);
            color: var(--ctp-text);
        }
        .form-control:focus, .form-select:focus {
            background-color: var(--ctp-surface0);
            border-color: var(--ctp-lavender);
            color: var(--ctp-text);
            box-shadow: 0 0 0 0.25rem rgba(180, 190, 254, 0.25);
        }
        .form-control::placeholder { color: var(--ctp-overlay2); }
        /* Form Checkboxes */
        .form-check-input {
            background-color: var(--ctp-surface0);
            border-color: var(--ctp-surface1);
        }
        .form-check-input:checked {
            background-color: var(--ctp-lavender);
            border-color: var(--ctp-lavender);
        }
        .form-check-input:focus {
            box-shadow: 0 0 0 0.25rem rgba(180, 190, 254, 0.25);
            border-color: var(--ctp-lavender);
        }
        /* Buttons */
        .btn-primary {
            background-color: var(--ctp-blue);
            border-color: var(--ctp-blue);
            color: var(--ctp-crust);
            font-weight: 600;
        }
        .btn-primary:hover, .btn-primary:focus {
            background-color: var(--ctp-lavender);
            border-color: var(--ctp-lavender);
            color: var(--ctp-crust);
        }
        /* Links */
        a { color: var(--ctp-rosewater); text-decoration: none; }
        a:hover { color: var(--ctp-lavender); text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card p-4">
            <h1 class="mb-4 text-center">Codebase Convert</h1>
            <p class="text-center text-muted mb-4">
                Convert a GitHub repository or local path to a single TXT, MD, or DOCX file. <br>
                <a href="/apidocs/">View Swagger API Docs</a>
            </p>
            <form id="convertForm" action="/api/form-convert" method="POST">
                <div class="mb-3">
                    <label for="input" class="form-label">GitHub URL or Local Path *</label>
                    <input type="text" class="form-control" id="input" name="input" placeholder="e.g. https://github.com/QaisarRajput/codebase_to_text" required>
                </div>
                <div class="row">
                    <div class="col-md-4 mb-3">
                        <label for="output" class="form-label">Output *</label>
                        <input type="text" class="form-control" id="output" name="output" placeholder="e.g. output.txt" required>
                    </div>
                    <div class="col-md-4 mb-3">
                        <label for="output_type" class="form-label">Output Type</label>
                        <select class="form-select" id="output_type" name="output_type">
                            <option value="txt">Text (.txt)</option>
                            <option value="md">Markdown (.md)</option>
                            <option value="docx">Word (.docx)</option>
                        </select>
                    </div>
                    <div class="col-md-4 mb-3">
                        <label for="exclude" class="form-label">Exclude Patterns</label>
                        <input type="text" class="form-control" id="exclude" name="exclude" placeholder="e.g. *.log, temp/">
                    </div>
                </div>
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="exclude_hidden" name="exclude_hidden">
                            <label class="form-check-label" for="exclude_hidden">Exclude Hidden</label>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="verbose" name="verbose">
                            <label class="form-check-label" for="verbose">Verbose</label>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="no_ai_optimize" name="no_ai_optimize">
                            <label class="form-check-label" for="no_ai_optimize">No AI Optimize</label>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="strip_comments" name="strip_comments">
                            <label class="form-check-label" for="strip_comments">Strip Comments</label>
                        </div>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary w-100" id="submitBtn">Convert & Download</button>
            </form>
            <div id="loading" class="text-center mt-3 d-none">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Processing codebase... Please wait.</p>
            </div>
            <div id="result" class="text-center mt-3 d-none">
                <div class="alert alert-success" role="alert" style="background-color: var(--ctp-surface0); border-color: var(--ctp-blue); color: var(--ctp-text);">
                    <strong>Success!</strong> Download started.<br>
                    <span id="tokenCountBadge" class="badge" style="background-color: var(--ctp-lavender); color: var(--ctp-crust); font-size: 1.1em; margin-top: 10px;"></span>
                </div>
            </div>
            <div id="aiReviewSection" class="mt-4 d-none text-start">
                <h5 class="mb-3 text-center">Ask AI for a Code Review</h5>
                <ul class="nav nav-pills mb-3 justify-content-center flex-wrap gap-2" id="pills-tab" role="tablist">
                  <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="pills-chatgpt-tab" data-bs-toggle="pill" data-bs-target="#pills-chatgpt" type="button" role="tab" style="color: #10a37f; font-weight: bold;">ChatGPT</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-claude-tab" data-bs-toggle="pill" data-bs-target="#pills-claude" type="button" role="tab" style="color: #d97757; font-weight: bold;">Claude</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-gemini-tab" data-bs-toggle="pill" data-bs-target="#pills-gemini" type="button" role="tab" style="color: #8ab4f8; font-weight: bold;">Gemini</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-deepseek-tab" data-bs-toggle="pill" data-bs-target="#pills-deepseek" type="button" role="tab" style="color: #4d6bfe; font-weight: bold;">DeepSeek</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-mistral-tab" data-bs-toggle="pill" data-bs-target="#pills-mistral" type="button" role="tab" style="color: #f54e42; font-weight: bold;">Mistral</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-perplexity-tab" data-bs-toggle="pill" data-bs-target="#pills-perplexity" type="button" role="tab" style="color: #22b8cd; font-weight: bold;">Perplexity</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-grok-tab" data-bs-toggle="pill" data-bs-target="#pills-grok" type="button" role="tab" style="color: #ffffff; font-weight: bold; background-color: #000; border: 1px solid #333;">Grok</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-meta-tab" data-bs-toggle="pill" data-bs-target="#pills-meta" type="button" role="tab" style="color: #0668E1; font-weight: bold;">Meta AI</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-huggingface-tab" data-bs-toggle="pill" data-bs-target="#pills-huggingface" type="button" role="tab" style="color: #FFD21E; font-weight: bold; text-shadow: 1px 1px 2px #000;">HuggingChat</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-poe-tab" data-bs-toggle="pill" data-bs-target="#pills-poe" type="button" role="tab" style="color: #7d5df6; font-weight: bold;">Poe</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-generic-tab" data-bs-toggle="pill" data-bs-target="#pills-generic" type="button" role="tab" style="color: #aaaaaa; font-weight: bold;">Other AI</button>
                  </li>
                </ul>
                <div class="tab-content" id="pills-tabContent">
                  <!-- ChatGPT Prompt -->
                  <div class="tab-pane fade show active" id="pills-chatgpt" role="tabpanel">
                      <textarea id="aiPromptTextChatGPT" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are an elite Systems Architect and Principal Software Engineer. I am providing you with the complete source code for a project. Your task is to perform an exhaustive, multi-step codebase review using your advanced reasoning capabilities.
INSTRUCTIONS:
1. INITIAL ASSESSMENT: Briefly summarize the overall architecture, intent, and tech stack of the codebase.
2. DEEP CODE REVIEW: Rigorously analyze the code across these critical dimensions:
   - Architecture & Design: Identify violations of SOLID principles, tight coupling, MVC/Clean architecture deviations, and poor abstractions.
   - Security & Resilience: Hunt for OWASP Top 10 vulnerabilities, injection flaws, insecure data handling, and lack of input sanitization.
   - Performance & Scalability: Pinpoint algorithmic inefficiencies (Big-O issues), memory leaks, N+1 queries, and synchronous blocking operations.
   - Code Quality & Maintainability: Highlight code smells, DRY principle violations, misleading naming conventions, and brittle logic pathways.
3. ACTIONABLE DELIVERABLES:
   - For every identified issue, you MUST specify the exact file name and context.
   - Do not give vague advice. Provide a concrete, highly optimized, and robust code rewrite for every flawed section as a strictly formatted code block.
   - End with a prioritized "Fix-It" roadmap mapping out immediate critical fixes vs. long-term technical debt reduction.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextChatGPT', this)">Copy Prompt</button>
                          <a href="https://chatgpt.com/" target="_blank" class="btn btn-outline-success" style="color: #10a37f; border-color: #10a37f;">Open ChatGPT</a>
                      </div>
                  </div>
                  <!-- Claude Prompt -->
                  <div class="tab-pane fade" id="pills-claude" role="tabpanel">
                      <textarea id="aiPromptTextClaude" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are a Staff-Level Software Engineer renowned for rigorous code reviews and vast context comprehension. I have attached a complete project codebase.
CONDUCT A COMPREHENSIVE AUDIT FOLLOWING THIS FRAMEWORK:
Phase 1: Architectural Integrity
Evaluate the structural layout, module boundaries, and dependency graph. Where will this architecture fail at scale? Are there cyclic dependencies or God classes?
Phase 2: Vulnerability & Robustness Analysis
Act as a security auditor. Find edge-case exploits, race conditions, concurrency issues, swallowed exceptions, unhandled states, and insecure dependencies.
Phase 3: Modernization & Optimization
Suggest modern language features, better design patterns, and algorithmic performance boosts. Scrutinize all loops and data structure choices for suboptimal time/space complexity.
OUTPUT FORMAT:
- Use markdown tables for a high-level summary of technical debt.
- Provide extreme deep-dives into specific files. 
- Whenever you suggest a change, you MUST provide the exact refactored code block with detailed comments explaining the engineering improvements. Do not return abstract summaries; return functional, secure, and production-ready code.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextClaude', this)">Copy Prompt</button>
                          <a href="https://claude.ai/" target="_blank" class="btn btn-outline-warning" style="color: #d97757; border-color: #d97757;">Open Claude</a>
                      </div>
                  </div>
                  <!-- Gemini Prompt -->
                  <div class="tab-pane fade" id="pills-gemini" role="tabpanel">
                      <textarea id="aiPromptTextGemini" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are an Expert Lead Developer with an exceptional ability to process massive codebase contexts. I am supplying my entire project's source code in the attached file.
REQUIREMENTS FOR COMPREHENSIVE REVIEW:
1. Holistic Architecture Review: How do the components interact? Trace the data flow and suggest decoupling strategies or architectural paradigm shifts if needed.
2. Deep Pattern Analysis: Scan the entire dataset for anti-patterns, duplicated "spaghetti" code, and violations of idiomatic language standards.
3. Security & Performance Profiling: Identify resource-intensive bottlenecks, redundant database queries/API calls, and security gaps affecting data integrity.
4. Logic Verification: Verify core algorithms for state mutation errors and unhandled null/undefined values.
5. Refactoring Roadmap: Provide a prioritized, step-by-step roadmap to eliminate technical debt.
For every major critique, write out the exact optimized code implementation. Do not skip details. Rely on your deep context window to track variables and state deeply across multiple files, and point out cross-file inconsistencies.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextGemini', this)">Copy Prompt</button>
                          <a href="https://gemini.google.com/" target="_blank" class="btn btn-outline-info" style="color: #8ab4f8; border-color: #8ab4f8;">Open Gemini</a>
                      </div>
                  </div>
                  <!-- DeepSeek Prompt -->
                  <div class="tab-pane fade" id="pills-deepseek" role="tabpanel">
                      <textarea id="aiPromptTextDeepseek" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are DeepSeek, an AI optimized for advanced algorithmic reasoning, logic mapping, and pristine software engineering. Here is my complete codebase.
EXECUTE A METICULOUS, EXPERT-LEVEL REVIEW:
Step 1: Algorithmic Efficiency. Scrutinize all loops, recursion, data structure choices, and logic paths for suboptimal Big-O time/space complexity.
Step 2: Structural Soundness. Assess the modularity, separation of concerns, and typing strictness. 
Step 3: Bug Detection. Leverage your coding reasoning to find deep, hidden bugs, memory leaks, race conditions, and unhandled edge cases.
Step 4: Dependency & Security Audit. Highlight vectors for attack or problematic integrations.
OUTPUT RULES:
- Be highly technical and brutally honest.
- For every vulnerability, inefficiency, or structural flaw you find, output a perfectly formatted, production-grade refactored code snippet. 
- Explain exactly WHY your updated approach is mathematically, computationally, and logically superior to the original.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextDeepseek', this)">Copy Prompt</button>
                          <a href="https://chat.deepseek.com/" target="_blank" class="btn btn-outline-primary" style="color: #4d6bfe; border-color: #4d6bfe;">Open DeepSeek</a>
                      </div>
                  </div>
                  <!-- Mistral Prompt -->
                  <div class="tab-pane fade" id="pills-mistral" role="tabpanel">
                      <textarea id="aiPromptTextMistral" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are Mistral, a fast, efficient, and highly capable Principal AI Engineer. I have provided my entire software project in the attached single file.
I require a direct, no-nonsense code review focused strictly on engineering excellence.
FOCUS AREAS:
1. Critical Vulnerabilities & Logic Flaws: Find anything that could cause a crash, privilege escalation, memory leak, or security breach. Check data validation boundaries.
2. Structural Technical Debt: Identify spaghetti code, God classes, and over-engineered or missing abstractions.
3. Performance Bottlenecks: Point out inefficient I/O, poor asynchronous handling, heavy synchronous blocking, or unoptimized database usage.
4. Idiomatic Alignment: Ensure the syntax and functions used are strictly modern and native to the language's best practices.
DELIVERABLE: 
Skip the fluff. Give me a prioritized list of critical issues, followed immediately by the required refactored code blocks to fix them. Ensure all provided code is bulletproof and optimized.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextMistral', this)">Copy Prompt</button>
                          <a href="https://chat.mistral.ai/" target="_blank" class="btn btn-outline-danger" style="color: #f54e42; border-color: #f54e42;">Open Le Chat</a>
                      </div>
                  </div>
                  <!-- Perplexity Prompt -->
                  <div class="tab-pane fade" id="pills-perplexity" role="tabpanel">
                      <textarea id="aiPromptTextPerplexity" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are Perplexity, an AI assistant with deep web-enabled analytical capabilities and access to the absolute latest coding standards and CVE databases. I am giving you my full codebase in a single file context.
Please review my codebase and cross-reference it with modern, best-in-class software development practices:
1. Code standards & Modernization: Are there updated libraries, functions, or language features I should be utilizing instead? Is this code using deprecated methods?
2. Vulnerability Assessment: Check for common CVE patterns, injection risks, SSRF, XSS, and poor authentication implementations.
3. Architecture & Edge Cases: Does the module configuration make sense? Are there unhandled logic pathways that will break in edge scenarios?
4. Technical Debt: Outline the top 5 actionable items I should address to reduce technical debt right now.
OUTPUT:
Provide a highly structured, heavily detailed response. Include verbatim file paths, line context, and write the exact code replacements needed to modernize and secure the project.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextPerplexity', this)">Copy Prompt</button>
                          <a href="https://www.perplexity.ai/" target="_blank" class="btn btn-outline-info" style="color: #22b8cd; border-color: #22b8cd;">Open Perplexity</a>
                      </div>
                  </div>
                  <!-- Grok Prompt -->
                  <div class="tab-pane fade" id="pills-grok" role="tabpanel">
                      <textarea id="aiPromptTextGrok" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are Grok, an AI created by xAI. You are witty, rebellious, and an incredibly sharp, unapologetic software engineer. I'm dumping my entire codebase in the attached file.
Give me a brutally honest, highly technical, and exhaustive code review:
1. Bugs & Inefficiencies: Roast any glaring errors, O(n^2) logic masked as O(n), memory leaks, or terrible data structure choices.
2. Architecture & Patterns: Does the file structure make sense or is it an over-engineered mess? Point out DRY violations and tight coupling. Suggest real, scalable alternatives.
3. Security Vectoring: Point out any obvious vectors for attack. Evaluate input sanitization and error masking.
4. Refactoring Orders: Don't just complain—fix it.
DELIVERABLE: 
For every massive flaw you find, map out the exact file/function, explain why it's technically a disaster, and give me the exact clean, refactored code snippets needed to fix it. Be thorough.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextGrok', this)">Copy Prompt</button>
                          <a href="https://grok.com/" target="_blank" class="btn btn-outline-light" style="color: #ffffff; border-color: #ffffff;">Open Grok</a>
                      </div>
                  </div>
                  <!-- Meta AI Prompt -->
                  <div class="tab-pane fade" id="pills-meta" role="tabpanel">
                      <textarea id="aiPromptTextMeta" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are Meta AI (Llama), a state-of-the-art open-model AI assistant with top-tier coding capabilities. I have provided my entire software project below.
Please execute a deep contextual, file-by-file review of this project:
1. Performance Check: Identify areas where computational efficiency, memory management, or concurrency could be dramatically improved.
2. Logic Verification: Check the core algorithms and error handling strategies for edge-case failures, unhandled promises/futures, or state mutation bugs.
3. Architectural Integrity: Evaluate design pattern implementations. Recommend structural changes to reduce coupling and increase cohesion.
4. Security Audit: Scan for improper auth/auth logic, injection vulnerabilities, and weak validation boundaries.
OUTPUT: 
Generate a comprehensive technical report. Use strong formatting. For the 5 most critical sections that need improvement, output the exact refactored code blocks, clearly explaining how the new design resolves the systemic issues.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextMeta', this)">Copy Prompt</button>
                          <a href="https://www.meta.ai/" target="_blank" class="btn btn-outline-primary" style="color: #0668E1; border-color: #0668E1;">Open Meta AI</a>
                      </div>
                  </div>
                  <!-- HuggingChat AIs Prompt -->
                  <div class="tab-pane fade" id="pills-huggingface" role="tabpanel">
                      <textarea id="aiPromptTextHF" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are a state-of-the-art open-source AI assistant on HuggingChat, equipped with advanced programming logic. Attached is my full project codebase.
Read the entire file context carefully and perform an exhaustive, expert-level code review:
1. Code Organization: Evaluate module boundaries, dependency flow, and architectural scalability.
2. Anti-patterns & Smells: Point out any code smells, duplicated logic, or deviations from standard SOLID/clean design practices.
3. Edge Cases & Resilience: Identify scenarios where the logic might fail, deadlock, or crash unexpectedly. Verify null/error handling states.
4. Performance & Security: Check for sub-optimal query patterns, slow loops, memory retention issues, and insecure data handling.
Actionable Deliverables: 
Provide a prioritized list of high-impact refactorings. You must provide precise, fully refactored, and beautifully formatted code snippets to replace the problematic areas you discover.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextHF', this)">Copy Prompt</button>
                          <a href="https://huggingface.co/chat/" target="_blank" class="btn btn-outline-warning" style="color: #FFD21E; border-color: #FFD21E;">Open HuggingChat</a>
                      </div>
                  </div>
                  <!-- Poe AIs Prompt -->
                  <div class="tab-pane fade" id="pills-poe" role="tabpanel">
                      <textarea id="aiPromptTextPoe" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are a highly capable AI assistant on Poe. I'm providing you with the full text representation of my codebase below.
Please act as a Senior Systems Architect and review this code exhaustively:
1. Scalability & DB Operations: Tell me if the current structure will scale well under heavy load. Highlight performance bottlenecks like synchronous I/O or N+1 problems.
2. Structural Flaws: Point out tight coupling, missing abstractions, or messy horizontal dependencies. Review the directory/domain structure.
3. Security & Robustness: Highlight vulnerabilities (XSS, SQLi, improper bounds checking) or missing error management/logging frameworks.
4. Typing & Syntax: Enforce rigid type checking and modern idiomatic syntax.
OUTPUT TASK: 
Deliver a highly technical review. Group by "Critical Priority" and "Optimization Suggestions". Supply optimized, secure code snippets to act as immediate drop-in replacements for the problematic parts.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextPoe', this)">Copy Prompt</button>
                          <a href="https://poe.com/" target="_blank" class="btn btn-outline-info" style="color: #7d5df6; border-color: #7d5df6;">Open Poe</a>
                      </div>
                  </div>
                  <!-- Generic AI Prompt -->
                  <div class="tab-pane fade" id="pills-generic" role="tabpanel">
                      <textarea id="aiPromptTextGeneric" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are an elite Software Engineer and Systems Architect. I am providing you with the complete source code for a project. Your task is to perform an exhaustive, multi-step code review.
INSTRUCTIONS:
1. DEEP CODE REVIEW: Analyze the code across these critical dimensions:
   - Architecture & Design: Identify violations of SOLID principles, tight coupling, and poor abstraction mapping.
   - Security & Resilience: Hunt for vulnerabilities, insecure data handling, and lack of input sanitization.
   - Performance & Scalability: Pinpoint algorithmic inefficiencies, memory leaks, and blocking operations.
   - Code Quality & Clean Code: Highlight code smells, DRY principle violations, and confusing logic.
2. ACTIONABLE DELIVERABLES:
   - For each identified issue, specify the exact file name and logical context.
   - Provide a concrete, highly optimized, and robust code rewrite for every flawed section. Do not give vague theoretical advice; supply production-ready implementation snippets. End with a roadmap for reducing technical debt.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextGeneric', this)">Copy Prompt</button>
                      </div>
                  </div>
                </div>
                <p class="text-center text-muted mt-4" style="font-size: 0.85em;">Copy the prompt above, upload your converted file on the respective AI website, and paste the prompt to get a complete codebase review.</p>
            </div>
        </div>
    </div>
    <script>
        document.getElementById('convertForm').addEventListener('submit', async function(e) {
            e.preventDefault(); // Stop standard form submission
            const btn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            const resultMsg = document.getElementById('result');
            const tokenBadge = document.getElementById('tokenCountBadge');
            const form = e.target;
            btn.disabled = true;
            loading.classList.remove('d-none');
            resultMsg.classList.add('d-none');
            try {
                const response = await fetch(form.action, {
                    method: form.method,
                    body: new URLSearchParams(new FormData(form))
                });
                if (!response.ok) {
                    const text = await response.text();
                    alert("Error: " + text);
                    return;
                }
                // Extract file name from Content-Disposition if possible
                let filename = form.output.value.trim();
                const outputType = form.output_type.value;
                if(!filename.endsWith('.' + outputType)) {
                    filename += '.' + outputType;
                }
                // Get Token Count Header
                const tokenCount = response.headers.get('X-Token-Count');
                if (tokenCount) {
                    tokenBadge.textContent = 'Estimated Token Count: ~' + parseInt(tokenCount).toLocaleString();
                } else {
                    tokenBadge.textContent = 'Token count unavailable';
                }
                // Trigger download
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(downloadUrl);
                resultMsg.classList.remove('d-none');
                document.getElementById('aiReviewSection').classList.remove('d-none');
            } catch (err) {
                alert("Request failed: " + err.message);
            } finally {
                btn.disabled = false;
                loading.classList.add('d-none');
            }
        });
        function copyAiPrompt(elementId, btn) {
            const promptText = document.getElementById(elementId);
            promptText.select();
            promptText.setSelectionRange(0, 99999); /* For mobile devices */
            navigator.clipboard.writeText(promptText.value).then(() => {
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 2000);
            }).catch(err => {
                alert('Failed to copy prompt: ' + err);
            });
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```
### File: `tests\test_codebase_convert.py`
```python
import unittest
import os
import sys
import tempfile
import shutil
from pathlib import Path
# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from codebase_convert.codebase_convert import CodebaseConvert
class TestCodebaseConvert(unittest.TestCase):
    def setUp(self):
        """Set up test environment with temporary folder structure"""
        self.test_folder_path = tempfile.mkdtemp(prefix="test_codebase_")
        # Create test folder structure
        self._create_test_structure()
        # Output paths for testing
        self.output_txt = os.path.join(self.test_folder_path, "output.txt")
        self.output_docx = os.path.join(self.test_folder_path, "output.docx")
    def _create_test_structure(self):
        """Create a complex test folder structure"""
        base = self.test_folder_path
        # Create main files
        with open(os.path.join(base, "main.py"), "w") as f:
            f.write("print('Hello World')")
        with open(os.path.join(base, "README.md"), "w") as f:
            f.write("# Test Project\nThis is a test.")
        with open(os.path.join(base, "requirements.txt"), "w") as f:
            f.write("flask>=2.0.0\nflasgger>=0.9.5\npython-docx>=0.8.11\nPillow>=8.0.0\ngitpython>=3.1.0\npathspec>=0.9.0\ntiktoken>=0.3.0")
        # Create subdirectories
        os.makedirs(os.path.join(base, "src"), exist_ok=True)
        os.makedirs(os.path.join(base, "tests"), exist_ok=True)
        os.makedirs(os.path.join(base, "__pycache__"), exist_ok=True)
        os.makedirs(os.path.join(base, ".git"), exist_ok=True)
        os.makedirs(os.path.join(base, "venv", "lib"), exist_ok=True)
        os.makedirs(os.path.join(base, "logs"), exist_ok=True)
        # Create files in subdirectories
        with open(os.path.join(base, "src", "app.py"), "w") as f:
            f.write("def main():\n    pass")
        with open(os.path.join(base, "src", "utils.py"), "w") as f:
            f.write("def helper():\n    return True")
        with open(os.path.join(base, "tests", "test_app.py"), "w") as f:
            f.write("import unittest\n\nclass TestApp(unittest.TestCase):\n    pass")
        # Create files that should be excluded by default
        with open(os.path.join(base, "__pycache__", "app.cpython-39.pyc"), "w") as f:
            f.write("binary content")
        with open(os.path.join(base, ".git", "config"), "w") as f:
            f.write("[core]\nrepositoryformatversion = 0")
        with open(os.path.join(base, "venv", "lib", "python3.9"), "w") as f:
            f.write("virtual env file")
        with open(os.path.join(base, "logs", "app.log"), "w") as f:
            f.write("2023-01-01 10:00:00 INFO Application started")
        with open(os.path.join(base, "temp.tmp"), "w") as f:
            f.write("temporary content")
        # Create hidden files
        with open(os.path.join(base, ".gitignore"), "w") as f:
            f.write("*.pyc\n__pycache__/\n.env")
        with open(os.path.join(base, ".env"), "w") as f:
            f.write("SECRET_KEY=test123")
    def test_basic_functionality(self):
        """Test basic text generation without exclusions"""
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=[],
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        self.assertIn("Folder Structure", text)
        self.assertIn("File Contents", text)
        self.assertIn("main.py", text)
        self.assertIn("Hello World", text)
    def test_exclude_hidden_files(self):
        """Test exclusion of hidden files"""
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=True,
            exclude=[],
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        self.assertNotIn(".gitignore", text)
        self.assertNotIn(".env", text)
        self.assertIn("main.py", text)  # Regular files should still be included
    def test_exclude_patterns(self):
        """Test pattern-based exclusions"""
        exclude_patterns = ["*.log", "*.tmp", "__pycache__/**", ".git/**"]
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=exclude_patterns,
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        # Split the text to get only the folder structure section
        folder_structure_section = text.split("File Contents")[0]
        # Should exclude log and tmp files from folder structure
        self.assertNotIn("app.log", folder_structure_section)
        self.assertNotIn("temp.tmp", folder_structure_section)
        self.assertNotIn("__pycache__/", folder_structure_section)
        self.assertNotIn(".git/", folder_structure_section)
        # Should include normal files in folder structure
        self.assertIn("main.py", folder_structure_section)
        self.assertIn("src/", folder_structure_section)
    def test_exclude_specific_files(self):
        """Test exclusion of specific files"""
        exclude_patterns = ["README.md", "requirements.txt"]
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=exclude_patterns,
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
          # Should exclude specified files
        self.assertNotIn("README.md", text)
        self.assertNotIn("requirements.txt", text)
        # Should include other files
        self.assertIn("main.py", text)
    def test_exclude_directories(self):
        """Test exclusion of entire directories"""
        exclude_patterns = ["venv/", "logs/"]
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=exclude_patterns,
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        # Split the text to get only the folder structure section
        folder_structure_section = text.split("File Contents")[0]
        # Should exclude specified directories from folder structure
        self.assertNotIn("venv/", folder_structure_section)
        self.assertNotIn("logs/", folder_structure_section)
        # Should include other directories
        self.assertIn("src/", folder_structure_section)
        self.assertIn("tests/", folder_structure_section)
    def test_exclude_file_creation(self):
        """Test loading exclusion patterns from .exclude file"""
        exclude_file_path = os.path.join(self.test_folder_path, ".exclude")
        # Create .exclude file
        with open(exclude_file_path, "w") as f:
            f.write("# This is a comment\n")
            f.write("*.log\n")
            f.write("temp.tmp\n")
            f.write("venv/\n")
            f.write("\n")  # Empty line
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=[],
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        # Split the text to get only the folder structure section
        folder_structure_section = text.split("File Contents")[0]
        # Should exclude files listed in .exclude file from folder structure
        self.assertNotIn("app.log", folder_structure_section)
        self.assertNotIn("temp.tmp", folder_structure_section)
        self.assertNotIn("venv/", folder_structure_section)
    def test_combined_exclusions(self):
        """Test combination of CLI args and .exclude file"""
        exclude_file_path = os.path.join(self.test_folder_path, ".exclude")
        # Create .exclude file
        with open(exclude_file_path, "w") as f:
            f.write("*.log\n")
            f.write("venv/\n")
        # Also provide CLI exclusions
        cli_excludes = ["*.tmp", "__pycache__/"]
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=cli_excludes,
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        # Split the text to get only the folder structure section
        folder_structure_section = text.split("File Contents")[0]
        # Should exclude files from both sources from folder structure
        self.assertNotIn("app.log", folder_structure_section)  # From .exclude file
        self.assertNotIn("venv/", folder_structure_section)    # From .exclude file
        self.assertNotIn("temp.tmp", folder_structure_section) # From CLI
        self.assertNotIn("__pycache__/", folder_structure_section) # From CLI
    def test_output_file_generation_txt(self):
        """Test TXT file output generation"""
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=["*.log", "*.tmp"],
            ai_optimize=False,
            strip_comments=False
        ) as code_to_text:
            code_to_text.get_file()
        # Check if output file was created
        self.assertTrue(os.path.exists(self.output_txt))
        # Check content
        with open(self.output_txt, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Folder Structure", content)
            self.assertIn("main.py", content)
    def test_output_file_generation_docx(self):
        """Test DOCX file output generation"""
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_docx,
            output_type="docx",
            verbose=False,
            exclude_hidden=False,
            exclude=["*.log", "*.tmp"],
            ai_optimize=False,
            strip_comments=False
        ) as code_to_text:
            code_to_text.get_file()
        # Check if output file was created
        self.assertTrue(os.path.exists(self.output_docx))
    def test_verbose_mode(self):
        """Test verbose output mode"""
        with self.assertLogs('codebase_convert', level='DEBUG') as cm:
            with CodebaseConvert(
                input_path=self.test_folder_path,
                output_path=self.output_txt,
                output_type="txt",
                verbose=True,
                exclude_hidden=False,
                exclude=["*.log"],
                ai_optimize=False,
                strip_comments=False
            ) as code_to_text:
                code_to_text.get_file()
            output = "\\n".join(cm.output)
            # Should contain verbose messages
            self.assertIn("Active exclusion patterns", output)
            self.assertIn("Processing:", output)
    def test_invalid_output_type(self):
        """Test error handling for invalid output type"""
        with self.assertRaises(ValueError):
            with CodebaseConvert(
                input_path=self.test_folder_path,
                output_path="output.xyz",
                output_type="xyz",
                verbose=False,
                exclude_hidden=False,
                exclude=[],
                ai_optimize=False,
                strip_comments=False
            ) as code_to_text:
                code_to_text.get_file()    
    def test_exclusion_count_tracking(self):
        """Test that exclusion counting works correctly"""
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=True,  # Need verbose mode for this test to work properly
            exclude_hidden=False,
            exclude=["*.log", "*.tmp", "__pycache__/**"],
            ai_optimize=False,
            strip_comments=False
        ) as code_to_text:
            # Generate text to trigger exclusion counting
            code_to_text.get_text()
            # Should have excluded some files
            self.assertGreater(code_to_text.excluded_files_count, 0)
    def test_ai_optimize(self):
        """Test the new ai_optimize feature strips whitespace"""
        file_path = os.path.join(self.test_folder_path, "ai_test.py")
        with open(file_path, "w") as f:
            f.write("def func():\n    pass\n\n\n\n# test")
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            ai_optimize=True,
            strip_comments=False
        ) as code_to_text:
            text = code_to_text.get_text()
            self.assertIn("<file path", text) # Check strategy pattern applied ai framing
    def test_strip_comments(self):
        """Test the new strip_comments feature removed comments"""
        file_path = os.path.join(self.test_folder_path, "comment_test.py")
        with open(file_path, "w") as f:
            f.write("# this is a comment\ndef func():\n    pass")
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            ai_optimize=True,
            strip_comments=True
        ) as code_to_text:
            text = code_to_text.get_text()
            self.assertNotIn("this is a comment", text)
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_folder_path):
            shutil.rmtree(self.test_folder_path)
class TestPatternMatching(unittest.TestCase):
    """Test exclusion pattern matching specifically"""
    def setUp(self):
        self.test_folder_path = tempfile.mkdtemp(prefix="test_patterns_")
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path="dummy.txt",
            output_type="txt",
            exclude=[]
        ) as self.code_to_text:
            pass # just used to initialize it
        # Manually reconstruct the object since `with` block closes it for testing internals:
        self.code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path="dummy.txt",
            output_type="txt",
            exclude=[],
            ai_optimize=False,
            strip_comments=False
        )
    def test_wildcard_patterns(self):
        """Test wildcard pattern matching"""
        self.code_to_text.exclude_patterns = {"*.py", "*.log"}
        # Should match
        self.assertTrue(self.code_to_text._should_exclude("test.py", self.test_folder_path))
        self.assertTrue(self.code_to_text._should_exclude("app.log", self.test_folder_path))
        # Should not match
        self.assertFalse(self.code_to_text._should_exclude("test.txt", self.test_folder_path))
        self.assertFalse(self.code_to_text._should_exclude("README.md", self.test_folder_path))
    def test_directory_patterns(self):
        """Test directory pattern matching"""
        self.code_to_text.exclude_patterns = {"__pycache__/", "node_modules/"}
        # Create test directories
        pycache_dir = os.path.join(self.test_folder_path, "__pycache__")
        os.makedirs(pycache_dir, exist_ok=True)
        # Should match directories
        self.assertTrue(self.code_to_text._should_exclude(pycache_dir, self.test_folder_path))
    def test_recursive_patterns(self):
        """Test recursive wildcard patterns"""
        self.code_to_text.exclude_patterns = {"**/__pycache__/**", "**/node_modules/**"}
        # Create nested test structure
        nested_pycache = os.path.join(self.test_folder_path, "src", "utils", "__pycache__", "file.pyc")
        os.makedirs(os.path.dirname(nested_pycache), exist_ok=True)
        # Should match nested paths
        self.assertTrue(self.code_to_text._should_exclude(nested_pycache, self.test_folder_path))
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_folder_path):
            shutil.rmtree(self.test_folder_path)
class TestDocxImage(unittest.TestCase):
    def test_docx_with_image(self):
        import tempfile
        import os
        import base64
        from docx import Document
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write a dummy 1x1 PNG image
            img_path = os.path.join(temp_dir, "dummy.png")
            png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQAAAAA3bvkkAAAAC0lEQVQIW2NgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(png_data))
            # Create a new DOCX document and add a picture
            doc = Document()
            doc.add_paragraph("Testing DOCX image inclusion.")
            doc.add_picture(img_path)
            # Save the document
            doc_path = os.path.join(temp_dir, "test.docx")
            doc.save(doc_path)
            # Reload the document and assert that it contains an inline image
            new_doc = Document(doc_path)
            self.assertGreater(len(new_doc.inline_shapes), 0, "Document should contain at least one inline image.")
class TestImageCompression(unittest.TestCase):
    def test_image_compression(self):
        """Test images that compress into .txt format correctly"""
        import tempfile
        import os
        import base64
        from PIL import Image
        import io
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple 100x100 red PNG image
            img = Image.new('RGB', (100, 100), color='red')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_data = img_bytes.getvalue()
            # Write the image to a file
            img_path = os.path.join(temp_dir, "test_image.png")
            with open(img_path, "wb") as f:
                f.write(img_data)
            # Create a CodebaseConvert instance
            code_to_text = CodebaseConvert(
                input_path=temp_dir,
                output_path="dummy.txt",
                output_type="txt",
                verbose=False,
                exclude_hidden=False,
                exclude=[],
                ai_optimize=False,
                strip_comments=False
            )
            # Test compression to TXT format
            from codebase_convert.utils.image_utils import compress_image
            blob_bytes, mime_type = compress_image(img_path)
            self.assertIsNotNone(blob_bytes)
            self.assertEqual(mime_type, "image/jpeg")
            self.assertTrue(len(blob_bytes) > 0, "Compressed bytes should not be empty.")
if __name__ == "__main__":
    # Run specific test class or all tests
    unittest.main(verbosity=2)
```
### File: `tests\__init__.py`
```python
```
```

### File: `docs\README.md`

```markdown
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
```

### File: `templates\index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codebase Convert</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {
            /* Catppuccin Mocha Palette */
            --ctp-base: #1e1e2e;
            --ctp-mantle: #181825;
            --ctp-crust: #11111b;
            --ctp-text: #cdd6f4;
            --ctp-subtext1: #bac2de;
            --ctp-subtext0: #a6adc8;
            --ctp-overlay2: #9399b2;
            --ctp-overlay1: #7f849c;
            --ctp-surface2: #585b70;
            --ctp-surface1: #45475a;
            --ctp-surface0: #313244;
            --ctp-lavender: #b4befe;
            --ctp-blue: #89b4fa;
            --ctp-rosewater: #f5e0dc;
        }
        body { 
            padding: 40px; 
            background-color: var(--ctp-base); 
            color: var(--ctp-text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        h1, h2, h3, h4, h5, h6, p, .form-label, .form-check-label {
            color: var(--ctp-text) !important;
        }
        .card { 
            max-width: 800px; 
            margin: 0 auto; 
            background-color: var(--ctp-mantle);
            border: 1px solid var(--ctp-surface0);
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border-radius: 12px;
        }
        .text-muted { color: var(--ctp-overlay1) !important; }
        /* Form Inputs */
        .form-control, .form-select {
            background-color: var(--ctp-surface0);
            border: 1px solid var(--ctp-surface1);
            color: var(--ctp-text);
        }
        .form-control:focus, .form-select:focus {
            background-color: var(--ctp-surface0);
            border-color: var(--ctp-lavender);
            color: var(--ctp-text);
            box-shadow: 0 0 0 0.25rem rgba(180, 190, 254, 0.25);
        }
        .form-control::placeholder { color: var(--ctp-overlay2); }
        /* Form Checkboxes */
        .form-check-input {
            background-color: var(--ctp-surface0);
            border-color: var(--ctp-surface1);
        }
        .form-check-input:checked {
            background-color: var(--ctp-lavender);
            border-color: var(--ctp-lavender);
        }
        .form-check-input:focus {
            box-shadow: 0 0 0 0.25rem rgba(180, 190, 254, 0.25);
            border-color: var(--ctp-lavender);
        }
        /* Buttons */
        .btn-primary {
            background-color: var(--ctp-blue);
            border-color: var(--ctp-blue);
            color: var(--ctp-crust);
            font-weight: 600;
        }
        .btn-primary:hover, .btn-primary:focus {
            background-color: var(--ctp-lavender);
            border-color: var(--ctp-lavender);
            color: var(--ctp-crust);
        }
        /* Links */
        a { color: var(--ctp-rosewater); text-decoration: none; }
        a:hover { color: var(--ctp-lavender); text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card p-4">
            <h1 class="mb-4 text-center">Codebase Convert</h1>
            <p class="text-center text-muted mb-4">
                Convert a GitHub repository or local path to a single TXT, MD, or DOCX file. <br>
                <a href="/apidocs/">View Swagger API Docs</a>
            </p>
            <form id="convertForm" action="/api/form-convert" method="POST">
                <div class="mb-3">
                    <label for="input" class="form-label">GitHub URL or Local Path *</label>
                    <input type="text" class="form-control" id="input" name="input" placeholder="e.g. https://github.com/QaisarRajput/codebase_to_text" required>
                </div>
                <div class="row">
                    <div class="col-md-4 mb-3">
                        <label for="output" class="form-label">Output *</label>
                        <input type="text" class="form-control" id="output" name="output" placeholder="e.g. output.txt" required>
                    </div>
                    <div class="col-md-4 mb-3">
                        <label for="output_type" class="form-label">Output Type</label>
                        <select class="form-select" id="output_type" name="output_type">
                            <option value="txt">Text (.txt)</option>
                            <option value="md">Markdown (.md)</option>
                            <option value="docx">Word (.docx)</option>
                        </select>
                    </div>
                    <div class="col-md-4 mb-3">
                        <label for="exclude" class="form-label">Exclude Patterns</label>
                        <input type="text" class="form-control" id="exclude" name="exclude" placeholder="e.g. *.log, temp/">
                    </div>
                </div>
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="exclude_hidden" name="exclude_hidden">
                            <label class="form-check-label" for="exclude_hidden">Exclude Hidden</label>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="verbose" name="verbose">
                            <label class="form-check-label" for="verbose">Verbose</label>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="no_ai_optimize" name="no_ai_optimize">
                            <label class="form-check-label" for="no_ai_optimize">No AI Optimize</label>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="strip_comments" name="strip_comments">
                            <label class="form-check-label" for="strip_comments">Strip Comments</label>
                        </div>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary w-100" id="submitBtn">Convert & Download</button>
            </form>
            <div id="loading" class="text-center mt-3 d-none">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Processing codebase... Please wait.</p>
            </div>
            <div id="result" class="text-center mt-3 d-none">
                <div class="alert alert-success" role="alert" style="background-color: var(--ctp-surface0); border-color: var(--ctp-blue); color: var(--ctp-text);">
                    <strong>Success!</strong> Download started.<br>
                    <span id="tokenCountBadge" class="badge" style="background-color: var(--ctp-lavender); color: var(--ctp-crust); font-size: 1.1em; margin-top: 10px;"></span>
                </div>
            </div>
            <div id="aiReviewSection" class="mt-4 d-none text-start">
                <h5 class="mb-3 text-center">Ask AI for a Code Review</h5>
                <ul class="nav nav-pills mb-3 justify-content-center flex-wrap gap-2" id="pills-tab" role="tablist">
                  <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="pills-chatgpt-tab" data-bs-toggle="pill" data-bs-target="#pills-chatgpt" type="button" role="tab" style="color: #10a37f; font-weight: bold;">ChatGPT</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-claude-tab" data-bs-toggle="pill" data-bs-target="#pills-claude" type="button" role="tab" style="color: #d97757; font-weight: bold;">Claude</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-gemini-tab" data-bs-toggle="pill" data-bs-target="#pills-gemini" type="button" role="tab" style="color: #8ab4f8; font-weight: bold;">Gemini</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-deepseek-tab" data-bs-toggle="pill" data-bs-target="#pills-deepseek" type="button" role="tab" style="color: #4d6bfe; font-weight: bold;">DeepSeek</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-mistral-tab" data-bs-toggle="pill" data-bs-target="#pills-mistral" type="button" role="tab" style="color: #f54e42; font-weight: bold;">Mistral</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-perplexity-tab" data-bs-toggle="pill" data-bs-target="#pills-perplexity" type="button" role="tab" style="color: #22b8cd; font-weight: bold;">Perplexity</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-grok-tab" data-bs-toggle="pill" data-bs-target="#pills-grok" type="button" role="tab" style="color: #ffffff; font-weight: bold; background-color: #000; border: 1px solid #333;">Grok</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-meta-tab" data-bs-toggle="pill" data-bs-target="#pills-meta" type="button" role="tab" style="color: #0668E1; font-weight: bold;">Meta AI</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-huggingface-tab" data-bs-toggle="pill" data-bs-target="#pills-huggingface" type="button" role="tab" style="color: #FFD21E; font-weight: bold; text-shadow: 1px 1px 2px #000;">HuggingChat</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-poe-tab" data-bs-toggle="pill" data-bs-target="#pills-poe" type="button" role="tab" style="color: #7d5df6; font-weight: bold;">Poe</button>
                  </li>
                  <li class="nav-item" role="presentation">
                    <button class="nav-link" id="pills-generic-tab" data-bs-toggle="pill" data-bs-target="#pills-generic" type="button" role="tab" style="color: #aaaaaa; font-weight: bold;">Other AI</button>
                  </li>
                </ul>
                <div class="tab-content" id="pills-tabContent">
                  <!-- ChatGPT Prompt -->
                  <div class="tab-pane fade show active" id="pills-chatgpt" role="tabpanel">
                      <textarea id="aiPromptTextChatGPT" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are an elite Systems Architect and Principal Software Engineer. I am providing you with the complete source code for a project. Your task is to perform an exhaustive, multi-step codebase review using your advanced reasoning capabilities.
INSTRUCTIONS:
1. INITIAL ASSESSMENT: Briefly summarize the overall architecture, intent, and tech stack of the codebase.
2. DEEP CODE REVIEW: Rigorously analyze the code across these critical dimensions:
   - Architecture & Design: Identify violations of SOLID principles, tight coupling, MVC/Clean architecture deviations, and poor abstractions.
   - Security & Resilience: Hunt for OWASP Top 10 vulnerabilities, injection flaws, insecure data handling, and lack of input sanitization.
   - Performance & Scalability: Pinpoint algorithmic inefficiencies (Big-O issues), memory leaks, N+1 queries, and synchronous blocking operations.
   - Code Quality & Maintainability: Highlight code smells, DRY principle violations, misleading naming conventions, and brittle logic pathways.
3. ACTIONABLE DELIVERABLES:
   - For every identified issue, you MUST specify the exact file name and context.
   - Do not give vague advice. Provide a concrete, highly optimized, and robust code rewrite for every flawed section as a strictly formatted code block.
   - End with a prioritized "Fix-It" roadmap mapping out immediate critical fixes vs. long-term technical debt reduction.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextChatGPT', this)">Copy Prompt</button>
                          <a href="https://chatgpt.com/" target="_blank" class="btn btn-outline-success" style="color: #10a37f; border-color: #10a37f;">Open ChatGPT</a>
                      </div>
                  </div>
                  <!-- Claude Prompt -->
                  <div class="tab-pane fade" id="pills-claude" role="tabpanel">
                      <textarea id="aiPromptTextClaude" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are a Staff-Level Software Engineer renowned for rigorous code reviews and vast context comprehension. I have attached a complete project codebase.
CONDUCT A COMPREHENSIVE AUDIT FOLLOWING THIS FRAMEWORK:
Phase 1: Architectural Integrity
Evaluate the structural layout, module boundaries, and dependency graph. Where will this architecture fail at scale? Are there cyclic dependencies or God classes?
Phase 2: Vulnerability & Robustness Analysis
Act as a security auditor. Find edge-case exploits, race conditions, concurrency issues, swallowed exceptions, unhandled states, and insecure dependencies.
Phase 3: Modernization & Optimization
Suggest modern language features, better design patterns, and algorithmic performance boosts. Scrutinize all loops and data structure choices for suboptimal time/space complexity.
OUTPUT FORMAT:
- Use markdown tables for a high-level summary of technical debt.
- Provide extreme deep-dives into specific files. 
- Whenever you suggest a change, you MUST provide the exact refactored code block with detailed comments explaining the engineering improvements. Do not return abstract summaries; return functional, secure, and production-ready code.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextClaude', this)">Copy Prompt</button>
                          <a href="https://claude.ai/" target="_blank" class="btn btn-outline-warning" style="color: #d97757; border-color: #d97757;">Open Claude</a>
                      </div>
                  </div>
                  <!-- Gemini Prompt -->
                  <div class="tab-pane fade" id="pills-gemini" role="tabpanel">
                      <textarea id="aiPromptTextGemini" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are an Expert Lead Developer with an exceptional ability to process massive codebase contexts. I am supplying my entire project's source code in the attached file.
REQUIREMENTS FOR COMPREHENSIVE REVIEW:
1. Holistic Architecture Review: How do the components interact? Trace the data flow and suggest decoupling strategies or architectural paradigm shifts if needed.
2. Deep Pattern Analysis: Scan the entire dataset for anti-patterns, duplicated "spaghetti" code, and violations of idiomatic language standards.
3. Security & Performance Profiling: Identify resource-intensive bottlenecks, redundant database queries/API calls, and security gaps affecting data integrity.
4. Logic Verification: Verify core algorithms for state mutation errors and unhandled null/undefined values.
5. Refactoring Roadmap: Provide a prioritized, step-by-step roadmap to eliminate technical debt.
For every major critique, write out the exact optimized code implementation. Do not skip details. Rely on your deep context window to track variables and state deeply across multiple files, and point out cross-file inconsistencies.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextGemini', this)">Copy Prompt</button>
                          <a href="https://gemini.google.com/" target="_blank" class="btn btn-outline-info" style="color: #8ab4f8; border-color: #8ab4f8;">Open Gemini</a>
                      </div>
                  </div>
                  <!-- DeepSeek Prompt -->
                  <div class="tab-pane fade" id="pills-deepseek" role="tabpanel">
                      <textarea id="aiPromptTextDeepseek" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are DeepSeek, an AI optimized for advanced algorithmic reasoning, logic mapping, and pristine software engineering. Here is my complete codebase.
EXECUTE A METICULOUS, EXPERT-LEVEL REVIEW:
Step 1: Algorithmic Efficiency. Scrutinize all loops, recursion, data structure choices, and logic paths for suboptimal Big-O time/space complexity.
Step 2: Structural Soundness. Assess the modularity, separation of concerns, and typing strictness. 
Step 3: Bug Detection. Leverage your coding reasoning to find deep, hidden bugs, memory leaks, race conditions, and unhandled edge cases.
Step 4: Dependency & Security Audit. Highlight vectors for attack or problematic integrations.
OUTPUT RULES:
- Be highly technical and brutally honest.
- For every vulnerability, inefficiency, or structural flaw you find, output a perfectly formatted, production-grade refactored code snippet. 
- Explain exactly WHY your updated approach is mathematically, computationally, and logically superior to the original.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextDeepseek', this)">Copy Prompt</button>
                          <a href="https://chat.deepseek.com/" target="_blank" class="btn btn-outline-primary" style="color: #4d6bfe; border-color: #4d6bfe;">Open DeepSeek</a>
                      </div>
                  </div>
                  <!-- Mistral Prompt -->
                  <div class="tab-pane fade" id="pills-mistral" role="tabpanel">
                      <textarea id="aiPromptTextMistral" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are Mistral, a fast, efficient, and highly capable Principal AI Engineer. I have provided my entire software project in the attached single file.
I require a direct, no-nonsense code review focused strictly on engineering excellence.
FOCUS AREAS:
1. Critical Vulnerabilities & Logic Flaws: Find anything that could cause a crash, privilege escalation, memory leak, or security breach. Check data validation boundaries.
2. Structural Technical Debt: Identify spaghetti code, God classes, and over-engineered or missing abstractions.
3. Performance Bottlenecks: Point out inefficient I/O, poor asynchronous handling, heavy synchronous blocking, or unoptimized database usage.
4. Idiomatic Alignment: Ensure the syntax and functions used are strictly modern and native to the language's best practices.
DELIVERABLE: 
Skip the fluff. Give me a prioritized list of critical issues, followed immediately by the required refactored code blocks to fix them. Ensure all provided code is bulletproof and optimized.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextMistral', this)">Copy Prompt</button>
                          <a href="https://chat.mistral.ai/" target="_blank" class="btn btn-outline-danger" style="color: #f54e42; border-color: #f54e42;">Open Le Chat</a>
                      </div>
                  </div>
                  <!-- Perplexity Prompt -->
                  <div class="tab-pane fade" id="pills-perplexity" role="tabpanel">
                      <textarea id="aiPromptTextPerplexity" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are Perplexity, an AI assistant with deep web-enabled analytical capabilities and access to the absolute latest coding standards and CVE databases. I am giving you my full codebase in a single file context.
Please review my codebase and cross-reference it with modern, best-in-class software development practices:
1. Code standards & Modernization: Are there updated libraries, functions, or language features I should be utilizing instead? Is this code using deprecated methods?
2. Vulnerability Assessment: Check for common CVE patterns, injection risks, SSRF, XSS, and poor authentication implementations.
3. Architecture & Edge Cases: Does the module configuration make sense? Are there unhandled logic pathways that will break in edge scenarios?
4. Technical Debt: Outline the top 5 actionable items I should address to reduce technical debt right now.
OUTPUT:
Provide a highly structured, heavily detailed response. Include verbatim file paths, line context, and write the exact code replacements needed to modernize and secure the project.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextPerplexity', this)">Copy Prompt</button>
                          <a href="https://www.perplexity.ai/" target="_blank" class="btn btn-outline-info" style="color: #22b8cd; border-color: #22b8cd;">Open Perplexity</a>
                      </div>
                  </div>
                  <!-- Grok Prompt -->
                  <div class="tab-pane fade" id="pills-grok" role="tabpanel">
                      <textarea id="aiPromptTextGrok" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are Grok, an AI created by xAI. You are witty, rebellious, and an incredibly sharp, unapologetic software engineer. I'm dumping my entire codebase in the attached file.
Give me a brutally honest, highly technical, and exhaustive code review:
1. Bugs & Inefficiencies: Roast any glaring errors, O(n^2) logic masked as O(n), memory leaks, or terrible data structure choices.
2. Architecture & Patterns: Does the file structure make sense or is it an over-engineered mess? Point out DRY violations and tight coupling. Suggest real, scalable alternatives.
3. Security Vectoring: Point out any obvious vectors for attack. Evaluate input sanitization and error masking.
4. Refactoring Orders: Don't just complain—fix it.
DELIVERABLE: 
For every massive flaw you find, map out the exact file/function, explain why it's technically a disaster, and give me the exact clean, refactored code snippets needed to fix it. Be thorough.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextGrok', this)">Copy Prompt</button>
                          <a href="https://grok.com/" target="_blank" class="btn btn-outline-light" style="color: #ffffff; border-color: #ffffff;">Open Grok</a>
                      </div>
                  </div>
                  <!-- Meta AI Prompt -->
                  <div class="tab-pane fade" id="pills-meta" role="tabpanel">
                      <textarea id="aiPromptTextMeta" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are Meta AI (Llama), a state-of-the-art open-model AI assistant with top-tier coding capabilities. I have provided my entire software project below.
Please execute a deep contextual, file-by-file review of this project:
1. Performance Check: Identify areas where computational efficiency, memory management, or concurrency could be dramatically improved.
2. Logic Verification: Check the core algorithms and error handling strategies for edge-case failures, unhandled promises/futures, or state mutation bugs.
3. Architectural Integrity: Evaluate design pattern implementations. Recommend structural changes to reduce coupling and increase cohesion.
4. Security Audit: Scan for improper auth/auth logic, injection vulnerabilities, and weak validation boundaries.
OUTPUT: 
Generate a comprehensive technical report. Use strong formatting. For the 5 most critical sections that need improvement, output the exact refactored code blocks, clearly explaining how the new design resolves the systemic issues.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextMeta', this)">Copy Prompt</button>
                          <a href="https://www.meta.ai/" target="_blank" class="btn btn-outline-primary" style="color: #0668E1; border-color: #0668E1;">Open Meta AI</a>
                      </div>
                  </div>
                  <!-- HuggingChat AIs Prompt -->
                  <div class="tab-pane fade" id="pills-huggingface" role="tabpanel">
                      <textarea id="aiPromptTextHF" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are a state-of-the-art open-source AI assistant on HuggingChat, equipped with advanced programming logic. Attached is my full project codebase.
Read the entire file context carefully and perform an exhaustive, expert-level code review:
1. Code Organization: Evaluate module boundaries, dependency flow, and architectural scalability.
2. Anti-patterns & Smells: Point out any code smells, duplicated logic, or deviations from standard SOLID/clean design practices.
3. Edge Cases & Resilience: Identify scenarios where the logic might fail, deadlock, or crash unexpectedly. Verify null/error handling states.
4. Performance & Security: Check for sub-optimal query patterns, slow loops, memory retention issues, and insecure data handling.
Actionable Deliverables: 
Provide a prioritized list of high-impact refactorings. You must provide precise, fully refactored, and beautifully formatted code snippets to replace the problematic areas you discover.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextHF', this)">Copy Prompt</button>
                          <a href="https://huggingface.co/chat/" target="_blank" class="btn btn-outline-warning" style="color: #FFD21E; border-color: #FFD21E;">Open HuggingChat</a>
                      </div>
                  </div>
                  <!-- Poe AIs Prompt -->
                  <div class="tab-pane fade" id="pills-poe" role="tabpanel">
                      <textarea id="aiPromptTextPoe" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are a highly capable AI assistant on Poe. I'm providing you with the full text representation of my codebase below.
Please act as a Senior Systems Architect and review this code exhaustively:
1. Scalability & DB Operations: Tell me if the current structure will scale well under heavy load. Highlight performance bottlenecks like synchronous I/O or N+1 problems.
2. Structural Flaws: Point out tight coupling, missing abstractions, or messy horizontal dependencies. Review the directory/domain structure.
3. Security & Robustness: Highlight vulnerabilities (XSS, SQLi, improper bounds checking) or missing error management/logging frameworks.
4. Typing & Syntax: Enforce rigid type checking and modern idiomatic syntax.
OUTPUT TASK: 
Deliver a highly technical review. Group by "Critical Priority" and "Optimization Suggestions". Supply optimized, secure code snippets to act as immediate drop-in replacements for the problematic parts.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextPoe', this)">Copy Prompt</button>
                          <a href="https://poe.com/" target="_blank" class="btn btn-outline-info" style="color: #7d5df6; border-color: #7d5df6;">Open Poe</a>
                      </div>
                  </div>
                  <!-- Generic AI Prompt -->
                  <div class="tab-pane fade" id="pills-generic" role="tabpanel">
                      <textarea id="aiPromptTextGeneric" class="form-control mb-3" rows="12" readonly style="resize: none; background-color: var(--ctp-crust); color: var(--ctp-text); border: 1px solid var(--ctp-surface1);">You are an elite Software Engineer and Systems Architect. I am providing you with the complete source code for a project. Your task is to perform an exhaustive, multi-step code review.
INSTRUCTIONS:
1. DEEP CODE REVIEW: Analyze the code across these critical dimensions:
   - Architecture & Design: Identify violations of SOLID principles, tight coupling, and poor abstraction mapping.
   - Security & Resilience: Hunt for vulnerabilities, insecure data handling, and lack of input sanitization.
   - Performance & Scalability: Pinpoint algorithmic inefficiencies, memory leaks, and blocking operations.
   - Code Quality & Clean Code: Highlight code smells, DRY principle violations, and confusing logic.
2. ACTIONABLE DELIVERABLES:
   - For each identified issue, specify the exact file name and logical context.
   - Provide a concrete, highly optimized, and robust code rewrite for every flawed section. Do not give vague theoretical advice; supply production-ready implementation snippets. End with a roadmap for reducing technical debt.</textarea>
                      <div class="d-flex justify-content-center gap-2">
                          <button type="button" class="btn btn-secondary" style="background-color: var(--ctp-surface2); border: none; color: var(--ctp-crust); font-weight: 600;" onclick="copyAiPrompt('aiPromptTextGeneric', this)">Copy Prompt</button>
                      </div>
                  </div>
                </div>
                <p class="text-center text-muted mt-4" style="font-size: 0.85em;">Copy the prompt above, upload your converted file on the respective AI website, and paste the prompt to get a complete codebase review.</p>
            </div>
        </div>
    </div>
    <script>
        document.getElementById('convertForm').addEventListener('submit', async function(e) {
            e.preventDefault(); // Stop standard form submission
            const btn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            const resultMsg = document.getElementById('result');
            const tokenBadge = document.getElementById('tokenCountBadge');
            const form = e.target;
            btn.disabled = true;
            loading.classList.remove('d-none');
            resultMsg.classList.add('d-none');
            try {
                const response = await fetch(form.action, {
                    method: form.method,
                    body: new URLSearchParams(new FormData(form))
                });
                if (!response.ok) {
                    const text = await response.text();
                    alert("Error: " + text);
                    return;
                }
                // Extract file name from Content-Disposition if possible
                let filename = form.output.value.trim();
                const outputType = form.output_type.value;
                if(!filename.endsWith('.' + outputType)) {
                    filename += '.' + outputType;
                }
                // Get Token Count Header
                const tokenCount = response.headers.get('X-Token-Count');
                if (tokenCount) {
                    tokenBadge.textContent = 'Estimated Token Count: ~' + parseInt(tokenCount).toLocaleString();
                } else {
                    tokenBadge.textContent = 'Token count unavailable';
                }
                // Trigger download
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(downloadUrl);
                resultMsg.classList.remove('d-none');
                document.getElementById('aiReviewSection').classList.remove('d-none');
            } catch (err) {
                alert("Request failed: " + err.message);
            } finally {
                btn.disabled = false;
                loading.classList.add('d-none');
            }
        });
        function copyAiPrompt(elementId, btn) {
            const promptText = document.getElementById(elementId);
            promptText.select();
            promptText.setSelectionRange(0, 99999); /* For mobile devices */
            navigator.clipboard.writeText(promptText.value).then(() => {
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 2000);
            }).catch(err => {
                alert('Failed to copy prompt: ' + err);
            });
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

### File: `tests\test_codebase_convert.py`

```python
import unittest
import os
import sys
import tempfile
import shutil
from pathlib import Path
# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from codebase_convert.codebase_convert import CodebaseConvert
class TestCodebaseConvert(unittest.TestCase):
    def setUp(self):
        """Set up test environment with temporary folder structure"""
        self.test_folder_path = tempfile.mkdtemp(prefix="test_codebase_")
        # Create test folder structure
        self._create_test_structure()
        # Output paths for testing
        self.output_txt = os.path.join(self.test_folder_path, "output.txt")
        self.output_docx = os.path.join(self.test_folder_path, "output.docx")
    def _create_test_structure(self):
        """Create a complex test folder structure"""
        base = self.test_folder_path
        # Create main files
        with open(os.path.join(base, "main.py"), "w") as f:
            f.write("print('Hello World')")
        with open(os.path.join(base, "README.md"), "w") as f:
            f.write("# Test Project\nThis is a test.")
        with open(os.path.join(base, "requirements.txt"), "w") as f:
            f.write("flask>=2.0.0\nflasgger>=0.9.5\npython-docx>=0.8.11\nPillow>=8.0.0\ngitpython>=3.1.0\npathspec>=0.9.0\ntiktoken>=0.3.0")
        # Create subdirectories
        os.makedirs(os.path.join(base, "src"), exist_ok=True)
        os.makedirs(os.path.join(base, "tests"), exist_ok=True)
        os.makedirs(os.path.join(base, "__pycache__"), exist_ok=True)
        os.makedirs(os.path.join(base, ".git"), exist_ok=True)
        os.makedirs(os.path.join(base, "venv", "lib"), exist_ok=True)
        os.makedirs(os.path.join(base, "logs"), exist_ok=True)
        # Create files in subdirectories
        with open(os.path.join(base, "src", "app.py"), "w") as f:
            f.write("def main():\n    pass")
        with open(os.path.join(base, "src", "utils.py"), "w") as f:
            f.write("def helper():\n    return True")
        with open(os.path.join(base, "tests", "test_app.py"), "w") as f:
            f.write("import unittest\n\nclass TestApp(unittest.TestCase):\n    pass")
        # Create files that should be excluded by default
        with open(os.path.join(base, "__pycache__", "app.cpython-39.pyc"), "w") as f:
            f.write("binary content")
        with open(os.path.join(base, ".git", "config"), "w") as f:
            f.write("[core]\nrepositoryformatversion = 0")
        with open(os.path.join(base, "venv", "lib", "python3.9"), "w") as f:
            f.write("virtual env file")
        with open(os.path.join(base, "logs", "app.log"), "w") as f:
            f.write("2023-01-01 10:00:00 INFO Application started")
        with open(os.path.join(base, "temp.tmp"), "w") as f:
            f.write("temporary content")
        # Create hidden files
        with open(os.path.join(base, ".gitignore"), "w") as f:
            f.write("*.pyc\n__pycache__/\n.env")
        with open(os.path.join(base, ".env"), "w") as f:
            f.write("SECRET_KEY=test123")
    def test_basic_functionality(self):
        """Test basic text generation without exclusions"""
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=[],
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        self.assertIn("Folder Structure", text)
        self.assertIn("File Contents", text)
        self.assertIn("main.py", text)
        self.assertIn("Hello World", text)
    def test_exclude_hidden_files(self):
        """Test exclusion of hidden files"""
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=True,
            exclude=[],
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        self.assertNotIn(".gitignore", text)
        self.assertNotIn(".env", text)
        self.assertIn("main.py", text)  # Regular files should still be included
    def test_exclude_patterns(self):
        """Test pattern-based exclusions"""
        exclude_patterns = ["*.log", "*.tmp", "__pycache__/**", ".git/**"]
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=exclude_patterns,
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        # Split the text to get only the folder structure section
        folder_structure_section = text.split("File Contents")[0]
        # Should exclude log and tmp files from folder structure
        self.assertNotIn("app.log", folder_structure_section)
        self.assertNotIn("temp.tmp", folder_structure_section)
        self.assertNotIn("__pycache__/", folder_structure_section)
        self.assertNotIn(".git/", folder_structure_section)
        # Should include normal files in folder structure
        self.assertIn("main.py", folder_structure_section)
        self.assertIn("src/", folder_structure_section)
    def test_exclude_specific_files(self):
        """Test exclusion of specific files"""
        exclude_patterns = ["README.md", "requirements.txt"]
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=exclude_patterns,
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
          # Should exclude specified files
        self.assertNotIn("README.md", text)
        self.assertNotIn("requirements.txt", text)
        # Should include other files
        self.assertIn("main.py", text)
    def test_exclude_directories(self):
        """Test exclusion of entire directories"""
        exclude_patterns = ["venv/", "logs/"]
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=exclude_patterns,
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        # Split the text to get only the folder structure section
        folder_structure_section = text.split("File Contents")[0]
        # Should exclude specified directories from folder structure
        self.assertNotIn("venv/", folder_structure_section)
        self.assertNotIn("logs/", folder_structure_section)
        # Should include other directories
        self.assertIn("src/", folder_structure_section)
        self.assertIn("tests/", folder_structure_section)
    def test_exclude_file_creation(self):
        """Test loading exclusion patterns from .exclude file"""
        exclude_file_path = os.path.join(self.test_folder_path, ".exclude")
        # Create .exclude file
        with open(exclude_file_path, "w") as f:
            f.write("# This is a comment\n")
            f.write("*.log\n")
            f.write("temp.tmp\n")
            f.write("venv/\n")
            f.write("\n")  # Empty line
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=[],
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        # Split the text to get only the folder structure section
        folder_structure_section = text.split("File Contents")[0]
        # Should exclude files listed in .exclude file from folder structure
        self.assertNotIn("app.log", folder_structure_section)
        self.assertNotIn("temp.tmp", folder_structure_section)
        self.assertNotIn("venv/", folder_structure_section)
    def test_combined_exclusions(self):
        """Test combination of CLI args and .exclude file"""
        exclude_file_path = os.path.join(self.test_folder_path, ".exclude")
        # Create .exclude file
        with open(exclude_file_path, "w") as f:
            f.write("*.log\n")
            f.write("venv/\n")
        # Also provide CLI exclusions
        cli_excludes = ["*.tmp", "__pycache__/"]
        code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=cli_excludes,
            ai_optimize=False,
            strip_comments=False
        )
        text = code_to_text.get_text()
        # Split the text to get only the folder structure section
        folder_structure_section = text.split("File Contents")[0]
        # Should exclude files from both sources from folder structure
        self.assertNotIn("app.log", folder_structure_section)  # From .exclude file
        self.assertNotIn("venv/", folder_structure_section)    # From .exclude file
        self.assertNotIn("temp.tmp", folder_structure_section) # From CLI
        self.assertNotIn("__pycache__/", folder_structure_section) # From CLI
    def test_output_file_generation_txt(self):
        """Test TXT file output generation"""
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            exclude_hidden=False,
            exclude=["*.log", "*.tmp"],
            ai_optimize=False,
            strip_comments=False
        ) as code_to_text:
            code_to_text.get_file()
        # Check if output file was created
        self.assertTrue(os.path.exists(self.output_txt))
        # Check content
        with open(self.output_txt, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Folder Structure", content)
            self.assertIn("main.py", content)
    def test_output_file_generation_docx(self):
        """Test DOCX file output generation"""
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_docx,
            output_type="docx",
            verbose=False,
            exclude_hidden=False,
            exclude=["*.log", "*.tmp"],
            ai_optimize=False,
            strip_comments=False
        ) as code_to_text:
            code_to_text.get_file()
        # Check if output file was created
        self.assertTrue(os.path.exists(self.output_docx))
    def test_verbose_mode(self):
        """Test verbose output mode"""
        with self.assertLogs('codebase_convert', level='DEBUG') as cm:
            with CodebaseConvert(
                input_path=self.test_folder_path,
                output_path=self.output_txt,
                output_type="txt",
                verbose=True,
                exclude_hidden=False,
                exclude=["*.log"],
                ai_optimize=False,
                strip_comments=False
            ) as code_to_text:
                code_to_text.get_file()
            output = "\\n".join(cm.output)
            # Should contain verbose messages
            self.assertIn("Active exclusion patterns", output)
            self.assertIn("Processing:", output)
    def test_invalid_output_type(self):
        """Test error handling for invalid output type"""
        with self.assertRaises(ValueError):
            with CodebaseConvert(
                input_path=self.test_folder_path,
                output_path="output.xyz",
                output_type="xyz",
                verbose=False,
                exclude_hidden=False,
                exclude=[],
                ai_optimize=False,
                strip_comments=False
            ) as code_to_text:
                code_to_text.get_file()    
    def test_exclusion_count_tracking(self):
        """Test that exclusion counting works correctly"""
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=True,  # Need verbose mode for this test to work properly
            exclude_hidden=False,
            exclude=["*.log", "*.tmp", "__pycache__/**"],
            ai_optimize=False,
            strip_comments=False
        ) as code_to_text:
            # Generate text to trigger exclusion counting
            code_to_text.get_text()
            # Should have excluded some files
            self.assertGreater(code_to_text.excluded_files_count, 0)
    def test_ai_optimize(self):
        """Test the new ai_optimize feature strips whitespace"""
        file_path = os.path.join(self.test_folder_path, "ai_test.py")
        with open(file_path, "w") as f:
            f.write("def func():\n    pass\n\n\n\n# test")
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            ai_optimize=True,
            strip_comments=False
        ) as code_to_text:
            text = code_to_text.get_text()
            self.assertIn("<file path", text) # Check strategy pattern applied ai framing
    def test_strip_comments(self):
        """Test the new strip_comments feature removed comments"""
        file_path = os.path.join(self.test_folder_path, "comment_test.py")
        with open(file_path, "w") as f:
            f.write("# this is a comment\ndef func():\n    pass")
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path=self.output_txt,
            output_type="txt",
            verbose=False,
            ai_optimize=True,
            strip_comments=True
        ) as code_to_text:
            text = code_to_text.get_text()
            self.assertNotIn("this is a comment", text)
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_folder_path):
            shutil.rmtree(self.test_folder_path)
class TestPatternMatching(unittest.TestCase):
    """Test exclusion pattern matching specifically"""
    def setUp(self):
        self.test_folder_path = tempfile.mkdtemp(prefix="test_patterns_")
        with CodebaseConvert(
            input_path=self.test_folder_path,
            output_path="dummy.txt",
            output_type="txt",
            exclude=[]
        ) as self.code_to_text:
            pass # just used to initialize it
        # Manually reconstruct the object since `with` block closes it for testing internals:
        self.code_to_text = CodebaseConvert(
            input_path=self.test_folder_path,
            output_path="dummy.txt",
            output_type="txt",
            exclude=[],
            ai_optimize=False,
            strip_comments=False
        )
    def test_wildcard_patterns(self):
        """Test wildcard pattern matching"""
        self.code_to_text.exclude_patterns = {"*.py", "*.log"}
        # Should match
        self.assertTrue(self.code_to_text._should_exclude("test.py", self.test_folder_path))
        self.assertTrue(self.code_to_text._should_exclude("app.log", self.test_folder_path))
        # Should not match
        self.assertFalse(self.code_to_text._should_exclude("test.txt", self.test_folder_path))
        self.assertFalse(self.code_to_text._should_exclude("README.md", self.test_folder_path))
    def test_directory_patterns(self):
        """Test directory pattern matching"""
        self.code_to_text.exclude_patterns = {"__pycache__/", "node_modules/"}
        # Create test directories
        pycache_dir = os.path.join(self.test_folder_path, "__pycache__")
        os.makedirs(pycache_dir, exist_ok=True)
        # Should match directories
        self.assertTrue(self.code_to_text._should_exclude(pycache_dir, self.test_folder_path))
    def test_recursive_patterns(self):
        """Test recursive wildcard patterns"""
        self.code_to_text.exclude_patterns = {"**/__pycache__/**", "**/node_modules/**"}
        # Create nested test structure
        nested_pycache = os.path.join(self.test_folder_path, "src", "utils", "__pycache__", "file.pyc")
        os.makedirs(os.path.dirname(nested_pycache), exist_ok=True)
        # Should match nested paths
        self.assertTrue(self.code_to_text._should_exclude(nested_pycache, self.test_folder_path))
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_folder_path):
            shutil.rmtree(self.test_folder_path)
class TestDocxImage(unittest.TestCase):
    def test_docx_with_image(self):
        import tempfile
        import os
        import base64
        from docx import Document
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write a dummy 1x1 PNG image
            img_path = os.path.join(temp_dir, "dummy.png")
            png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQAAAAA3bvkkAAAAC0lEQVQIW2NgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(png_data))
            # Create a new DOCX document and add a picture
            doc = Document()
            doc.add_paragraph("Testing DOCX image inclusion.")
            doc.add_picture(img_path)
            # Save the document
            doc_path = os.path.join(temp_dir, "test.docx")
            doc.save(doc_path)
            # Reload the document and assert that it contains an inline image
            new_doc = Document(doc_path)
            self.assertGreater(len(new_doc.inline_shapes), 0, "Document should contain at least one inline image.")
class TestImageCompression(unittest.TestCase):
    def test_image_compression(self):
        """Test images that compress into .txt format correctly"""
        import tempfile
        import os
        import base64
        from PIL import Image
        import io
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple 100x100 red PNG image
            img = Image.new('RGB', (100, 100), color='red')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_data = img_bytes.getvalue()
            # Write the image to a file
            img_path = os.path.join(temp_dir, "test_image.png")
            with open(img_path, "wb") as f:
                f.write(img_data)
            # Create a CodebaseConvert instance
            code_to_text = CodebaseConvert(
                input_path=temp_dir,
                output_path="dummy.txt",
                output_type="txt",
                verbose=False,
                exclude_hidden=False,
                exclude=[],
                ai_optimize=False,
                strip_comments=False
            )
            # Test compression to TXT format
            from codebase_convert.utils.image_utils import compress_image
            blob_bytes, mime_type = compress_image(img_path)
            self.assertIsNotNone(blob_bytes)
            self.assertEqual(mime_type, "image/jpeg")
            self.assertTrue(len(blob_bytes) > 0, "Compressed bytes should not be empty.")
if __name__ == "__main__":
    # Run specific test class or all tests
    unittest.main(verbosity=2)
```

### File: `tests\__init__.py`

```python

```
