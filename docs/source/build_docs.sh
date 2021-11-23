#!/usr/bin/env bash
###############################################################################
# PURPOSE:
# Uses Sphinx with autodoc and chalicedoc plugins to generate pretty HTML
# documentation from docstrings in source/dataplaneapi/runtime/app.py and
# source/controlplaneapi/runtime/app.py. Output docs will be saved to docs/source/output/.
#
#
# PRELIMINARY:
#  python3 must be installed.
#
# USAGE:
#  ./build_docs.sh
#  open output/index.html
#
###############################################################################

# Create and activate a temporary Python environment for this script.
echo "------------------------------------------------------------------------------"
echo "Creating a temporary Python virtualenv for this script"
echo "------------------------------------------------------------------------------"



python -c "import os; print (os.getenv('VIRTUAL_ENV'))" | grep -q None
if [ $? -ne 0 ]; then
    echo "ERROR: Do not run this script inside Virtualenv. Type \`deactivate\` and run again.";
    exit 1;
fi
which python3
if [ $? -ne 0 ]; then
    echo "ERROR: install Python3 before running this script"
    exit 1
fi
VENV=$(mktemp -d)
python3 -m venv $VENV
source $VENV/bin/activate.fish
pip3 install sphinx boto3 chalice chalicedoc autodoc jsonschema PyJWT==2.1.0 rsa==4.7.2

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install required Python libraries."
    exit 1
fi

sphinx-build -b html . ./output