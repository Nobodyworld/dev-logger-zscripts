# zscripts/config.py
from __future__ import annotations

from pathlib import Path

# Define the directories to skip (deduplicated while preserving order)
SKIP_DIRS = tuple(
    dict.fromkeys(
        [
            "zscripts",
            "zbuild",
            "migrations",
            "static",
            "yayay",
            "asgi",
            "wsgi",
            "staticfiles",
            "logs",
            "media",
            "__pycache__",
            "build",
            "dist",
            "venv",
            "env",
            "envs",
            "node_modules",
            "public",
            "assets",
            ".git.txt",
        ]
    )
)

# Define the file types to look for and their corresponding output files
FILE_TYPES = {
    "admin.py": "admin_files",
    #"api_views.py": "api_views_files",
    "apps.py": "apps_files",
    "forms.py": "forms_files",
    #"handlers.py": "handlers_files",
    #"middleware.py": "middleware_files",
    "models.py": "models_files",
    #"permissions.py": "permissions_files",
    #"serializers.py": "serializers_files",
    #"services.py": "services_files",
    "signals.py": "signals_files",
    #"tasks.py": "tasks_files",
    "tests.py": "tests_files",
    "urls.py": "urls_files",
    "views.py": "views_files",
    "utils.py": "utils_files",
    #"constants.py": "constants_files",
    #"context_processors.py": "context_processors_files",
    #"decorators.py": "decorators_files",
    #"exceptions.py": "exceptions_files",
    #"helpers.py": "helpers_files",
    #"mixins.py": "mixins_files",
    #"settings.py": "settings_files",
    #"custom_tags.py": "tag_files",
    #"utilities.py": "utilities_files",
    #"validators.py": "validators_files",
    #"factories.py": "factories_files",
}

# Define directories for logging and output
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
LOG_DIR = SCRIPT_DIR / 'logs'
BUILD_DIR = LOG_DIR / 'build_files'
ANALYSIS_DIR = LOG_DIR / 'analysis_logs'
CONSOLIDATION_DIR = LOG_DIR / 'consoli_files'
WORK_DIR = LOG_DIR / 'logs_files'
TREE_LOG_DIR = LOG_DIR / 'logs_tree'

# Define log directories for specific file types
ALL_LOG_DIR = LOG_DIR / 'logs_apps_all'
PYTHON_LOG_DIR = LOG_DIR / 'logs_apps_pyth'
HTML_LOG_DIR = LOG_DIR / 'logs_apps_html'
CSS_LOG_DIR = LOG_DIR / 'logs_apps_css'
JS_LOG_DIR = LOG_DIR / 'logs_apps_js'
BOTH_LOG_DIR = LOG_DIR / 'logs_apps_both'
SINGLE_LOG_DIR = LOG_DIR / 'logs_single_files'

# Define the single file log name
CAPTURE_ALL_PYTHON_LOG = SINGLE_LOG_DIR / 'capture_all_pyth.txt'
CAPTURE_ALL_HTML_LOG = SINGLE_LOG_DIR / 'capture_all_html.txt'
CAPTURE_ALL_CSS_LOG = SINGLE_LOG_DIR / 'capture_all_css.txt'
CAPTURE_ALL_JS_LOG = SINGLE_LOG_DIR / 'capture_all_js.txt'
CAPTURE_ALL_PYTHON_HTML_LOG = SINGLE_LOG_DIR / 'capture_all_python_html.txt'
CAPTURE_ALL_LOG = SINGLE_LOG_DIR / 'capture_all.txt'

# Preset mappings used by the CLI to avoid scattering file-type knowledge
FILE_TYPE_PRESETS = {
    "python": {".py"},
    "html": {".html"},
    "css": {".css"},
    "javascript": {".js"},
    "python-html": {".py", ".html"},
    "all": {".py", ".html", ".css", ".js"},
}
