"""Define locations of directories to use.

 - TOP_CODE_DIR: the directory holding this module.
 - CLIENT_SECRETS_PATH: path to the file holding the client secrets JSON (see
   README).
 - RUNTIME_SECRETS_DIR: directory for holding secrets generated at runtime.
 - CACHE_DIR: directory to cache information in.

"""
import os

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The file with the OAuth 2.0 Client details.  This should be a "Client ID for
# native application", which can be created and downloaded at the google
# developers console (https://console.developers.google.com).  See README for
# more infomation.
CLIENT_SECRETS_PATH = os.path.join(CODE_DIR, "client_secrets.json")

RUNTIME_SECRETS_DIR = os.path.join(CODE_DIR, "generated_secrets")

CACHE_DIR = os.path.join(CODE_DIR, "cache")
