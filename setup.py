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
    long_description=open("README.md", "r", encoding="utf-8").read(),
    download_url="https://github.com/Misterscan/codebase_to_text/archive/refs/tags/2.0.0.tar.gz",
    long_description_content_type="text/markdown",
    keywords = ["codebase, code conversion, text conversion, folder structure, file contents, text extraction, document conversion, Python package, GitHub repository, command-line tool, code analysis, file parsing, code documentation, formatting preservation, readability"],
    
    url="https://github.com/Misterscan/codebase_to_text",
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
