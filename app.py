import os
import tempfile
import tiktoken
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

    # Use a secure temp file to generate output 
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_type}") as temp_out:
        output_file = temp_out.name
        
    try:
        # Initialize converter
        converter = CodebaseConvert(
            input_path=input_path,
            output_path=output_file,
            output_type=output_type,
            exclude=exclude,
            exclude_hidden=exclude_hidden,
            ai_optimize=ai_optimize,
            strip_comments=strip_comments,
            verbose=verbose
        )
        
        # Execute the conversion
        converter.get_file()
        
        # Send the file to the user
        return send_file(
            output_file, 
            as_attachment=True, 
            download_name=f"codebase_output.{output_type}"
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_type}") as temp_out:
        output_file = temp_out.name
        
    try:
        converter = CodebaseConvert(
            input_path=input_path,
            output_path=output_file,
            output_type=output_type,
            exclude=exclude,
            exclude_hidden=exclude_hidden,
            ai_optimize=ai_optimize,
            strip_comments=strip_comments,
            verbose=verbose
        )
        converter.get_file()
        
        # Calculate tokens
        content = converter.get_text()
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            token_count = len(enc.encode(content, disallowed_special=()))
        except Exception:
            token_count = 0
            
        response = send_file(
            output_file, 
            as_attachment=True, 
            download_name=download_filename
        )
        
        response.headers['X-Token-Count'] = str(token_count)
        response.headers['Access-Control-Expose-Headers'] = 'X-Token-Count'
        
        return response
    except Exception as e:
        return f"Conversion failed: {str(e)}", 500

if __name__ == '__main__':
    # Add an explicit port mapping. Runs on http://127.0.0.1:5003 by default.
    app.run(debug=True, host='0.0.0.0', port=5003)
