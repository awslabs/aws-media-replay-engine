# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('../source'))

# -- Project information -----------------------------------------------------

project = 'Media Replay Engine'
copyright = '2022, AWS'
author = 'AWS'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon', 'chalicedoc']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', '_templates']

# The master toctree document.
master_doc = 'index'

pygments_style = 'sphinx'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'smithy'
html_theme_path = ['./theme']
# html_theme_options = {'ga_id': os.environ.get('_CHALICE_GA_ID', '')}

html_title = 'AWS Media Replay Engine'
# A shorter title for the navigation bar.  Default is the same as html_title.
html_short_title = 'MRE'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']
os.environ["CLIP_GENERATION_STATE_MACHINE_ARN"] = "CLIP_GENERATION_STATE_MACHINE_ARN"
os.environ["FRAMEWORK_VERSION"] = "FRAMEWORK_VERSION"
os.environ["SYSTEM_TABLE_NAME"] = "SYSTEM_TABLE_NAME"

os.environ['CONTENT_GROUP_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['PROGRAM_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['PLUGIN_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['PLUGIN_NAME_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['PLUGIN_VERSION_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['PROFILE_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['MODEL_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['MODEL_NAME_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['MODEL_VERSION_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['EVENT_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['EVENT_CHANNEL_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['EVENT_PROGRAMID_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['EVENT_CONTENT_GROUP_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['EVENT_PAGINATION_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['WORKFLOW_EXECUTION_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['REPLAY_REQUEST_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['MEDIASOURCE_S3_BUCKET'] = "SYSTEM_TABLE_NAME"
os.environ['PROBE_VIDEO_LAMBDA_ARN'] = "SYSTEM_TABLE_NAME"
os.environ['MULTI_CHUNK_HELPER_LAMBDA_ARN'] = "SYSTEM_TABLE_NAME"
os.environ['PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN'] = "SYSTEM_TABLE_NAME"
os.environ['WORKFLOW_ERROR_HANDLER_LAMBDA_ARN'] = "SYSTEM_TABLE_NAME"
os.environ['SFN_ROLE_ARN'] = "SYSTEM_TABLE_NAME"
os.environ['EB_EVENT_BUS_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['SQS_QUEUE_URL'] = "SYSTEM_TABLE_NAME"
os.environ['HLS_HS256_API_AUTH_SECRET_KEY_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['CLOUDFRONT_COOKIE_PRIVATE_KEY_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['CLOUDFRONT_COOKIE_KEY_PAIR_ID_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['HLS_STREAM_CLOUDFRONT_DISTRO'] = "SYSTEM_TABLE_NAME"
os.environ['CURRENT_EVENTS_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['PROGRAM_EVENT_PLUGIN_INDEX'] = "PROGRAM_EVENT_PLUGIN_INDEX"



os.environ['FRAME_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['CHUNK_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['CHUNK_STARTPTS_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['PLUGIN_RESULT_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['CLIP_PREVIEW_FEEDBACK_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['EB_EVENT_BUS_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['REPLAY_RESULT_TABLE_NAME'] = "SYSTEM_TABLE_NAME"
os.environ['PROGRAM_EVENT_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX'] = "SYSTEM_TABLE_NAME"
os.environ['SERVICE_DISC_SERVICE_ID'] = 'SERVICE_DISC_SERVICE_ID'
os.environ['API_AUTH_SECRET_KEY_NAME'] = 'API_AUTH_SECRET_KEY_NAME'
os.environ['TRIGGER_LAMBDA_ARN'] = 'TRIGGER_LAMBDA_ARN'
