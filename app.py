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
