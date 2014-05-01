"""Handle authentication with google.

"""

import gapy.client
import oauth2client.tools
import os
from .dirs import CLIENT_SECRETS_PATH, RUNTIME_SECRETS_DIR

# A file which will be used to store the generated tokens produced after the
# oauth flow succeeds.  This should be kept secret, and includes a refresh
# token to refresh the oauth authorisation when required.
CLIENT_STORAGE = os.path.join(RUNTIME_SECRETS_DIR, 'storage.json')


def perform_auth():
    """Authenticate with the GA API.

    Returns a gapy.Client object.

    """
    # Prevent oauth2client from trying to open a browser
    # This is run from inside the VM so there is no browser
    oauth2client.tools.FLAGS.auth_local_webserver = False

    # We only want to request readonly access to analytics.  gapy doesn't have
    # any way to request this other than by monkeypatching it, sadly.
    gapy.client.GOOGLE_API_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

    assert os.path.isfile(CLIENT_SECRETS_PATH)
    if not os.path.isdir(RUNTIME_SECRETS_DIR):
        os.makedirs(RUNTIME_SECRETS_DIR)

    return gapy.client.from_secrets_file(
        CLIENT_SECRETS_PATH,
        storage_path=CLIENT_STORAGE,
    )
