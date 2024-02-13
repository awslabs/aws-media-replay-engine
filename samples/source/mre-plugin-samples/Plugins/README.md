**MRE Plugin Samples**

Plugin samples are provided to speed development and provide insights into different approaches for solving various video and audio processing needs. Plugins are written in Python 3.11 since the required MRE Helper library (Lambda Layer) is tested for this version.

Each plugin is organized in this repository in a folder based on it's unique name.

Each plugin folder contains:
- README.md
- config.json
- some-lambda-function.py
- optional-other-files

The plugin README should include the following details:
- The intended MRE Plugin Class
- Description of what the plugin is designed to do
- Use cases that describe how it was applied in earlier use
- Python dependencies with notes as to which need to be a custom Lambda Layer
- Model dependencies
- Other plugin dependencies referenced by name in this repo
- Expected parameter inputs and their purpose with sample values
- Expected output attributes (the data produced)
- IAM permissions needed (least privilege)
