#!/bin/bash

SCRIPT=$(readlink -f "$0")
SCRIPTDIR=$(dirname "$SCRIPT")

. "$SCRIPTDIR/../ENV/bin/activate"
python "$SCRIPTDIR/fetch.py" "$@"
