import os
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, request, jsonify, send_file, render_template, after_this_request
from flasgger import Swagger
from codebase_convert.codebase_convert import CodebaseConvert
from codebase_convert.utils.fs_utils import walk_filesystem_generator

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

# Root directory for path traversal checks. 
# We use the parent directory of the current workspace to allow users to select other local projects.
WORKSPACE_DIR = Path(os.getcwd()).resolve().parent

def _safe_input_path(input_path: str) -> bool:
    # Allow explicit GitHub forms
    if input_path.startswith("https://github.com/") or input_path.startswith("git@github.com:"):
        return True

    parsed = urlparse(input_path)
    # Block URL schemes to prevent SSRF, but allow single-letter 'schemes' (Windows drive letters)
    if parsed.scheme and len(parsed.scheme) > 1 and parsed.scheme in ("http", "https", "ftp", "ssh", "git"):
        return False

    try:
        target = Path(input_path)
        # On Windows, a path starting with / or \ is considered absolute but has no drive.
        # We want to treat such paths as relative to our WORKSPACE_DIR (the Documents folder).
        if not target.is_absolute() or (target.is_absolute() and not target.drive and (input_path.startswith('/') or input_path.startswith('\\'))):
            target = WORKSPACE_DIR / input_path.lstrip('/\\')
            
        target = target.resolve()
        
        # Robust path containment check using lower-case string comparison to handle Windows case-insensitivity
        # and drive letter variations reliably.
        target_str = str(target).lower()
        workspace_str = str(WORKSPACE_DIR).lower()
        
        return target_str == workspace_str or target_str.startswith(workspace_str + os.sep)
    except Exception:
        return False


def _process_conversion(input_path, output_type, exclude, exclude_hidden, ai_optimize, strip_comments, verbose, is_json, download_filename=None):
    if not _safe_input_path(input_path):
        err = "Path traversal detected or invalid path."
        return (jsonify({"error": err}), 403) if is_json else (err, 403)

    tmpdir = tempfile.mkdtemp(prefix="convert_")
    output_file = os.path.join(tmpdir, f"output.{output_type}")

    @after_this_request
    def cleanup(response):
        shutil.rmtree(tmpdir, ignore_errors=True)
        return response

    try:
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
            text_output = converter.get_text()
            converter.get_file(text_output=text_output)
            
            from codebase_convert.utils.utils import estimate_tokens
            token_count = estimate_tokens(text_output, verbose=verbose) or 0
            
            # Send the generated file with token count header
            response = send_file(
                output_file,
                as_attachment=True,
                download_name=download_filename or f"output.{output_type}"
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

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5003"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app.run(debug=debug, host=host, port=port)
