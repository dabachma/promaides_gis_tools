"""

"""

# system modules
import os
import tempfile


BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(BASE_DIR, 'ui')
DEPLOY_DIR = os.path.join(BASE_DIR, 'versions')
TMP_DEPLOY_DIR = os.path.join(tempfile.gettempdir(), 'promaides_gis_tools')

JSON_DIR = os.path.join(BASE_DIR, "json")

def get_ui_path(filename):
    path = os.path.join(UI_DIR, filename)
    if not os.path.exists(path) and not filename.endswith('.ui'):
        path = os.path.join(UI_DIR, filename + '.ui')
        if not os.path.exists(path):
            raise OSError('Given ui file "{}" does not exist in ui dir "{}"'.format(filename, BASE_DIR))
    return path

def get_json_path(filename):
    path = os.path.join(JSON_DIR, filename)
    return path
