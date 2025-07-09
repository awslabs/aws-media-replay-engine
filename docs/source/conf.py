#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

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

sys.path.insert(0, os.path.abspath("../source"))

# -- Project information -----------------------------------------------------

project = "Media Replay Engine"
copyright = "2022, AWS"
author = "AWS"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "chalicedoc"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "_templates"]

# The master toctree document.
master_doc = "index"

pygments_style = "sphinx"

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "smithy"
html_theme_path = ["./theme"]
# html_theme_options = {'ga_id': os.environ.get('_CHALICE_GA_ID', '')}

html_title = "AWS Media Replay Engine"
# A shorter title for the navigation bar.  Default is the same as html_title.
html_short_title = "MRE"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']
os.environ["CLIP_GENERATION_STATE_MACHINE_ARN"] = "CLIP_GENERATION_STATE_MACHINE_ARN"
os.environ["FRAMEWORK_VERSION"] = "FRAMEWORK_VERSION"
os.environ["SYSTEM_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["METADATA_TABLE_NAME"] = "METADATA_TABLE_NAME"

os.environ["CONTENT_GROUP_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["PROGRAM_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["PLUGIN_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["PLUGIN_NAME_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["PLUGIN_VERSION_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["PROFILE_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["MODEL_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["MODEL_NAME_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["MODEL_VERSION_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["EVENT_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["EVENT_CHANNEL_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["EVENT_PROGRAMID_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["EVENT_CONTENT_GROUP_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["EVENT_PAGINATION_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["WORKFLOW_EXECUTION_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["REPLAY_REQUEST_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["MEDIASOURCE_S3_BUCKET"] = "SYSTEM_TABLE_NAME"
os.environ["PROBE_VIDEO_LAMBDA_ARN"] = "SYSTEM_TABLE_NAME"
os.environ["MULTI_CHUNK_HELPER_LAMBDA_ARN"] = "SYSTEM_TABLE_NAME"
os.environ["PLUGIN_OUTPUT_HANDLER_LAMBDA_ARN"] = "SYSTEM_TABLE_NAME"
os.environ["WORKFLOW_ERROR_HANDLER_LAMBDA_ARN"] = "SYSTEM_TABLE_NAME"
os.environ["SFN_ROLE_ARN"] = "SYSTEM_TABLE_NAME"
os.environ["EB_EVENT_BUS_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["SQS_QUEUE_URL"] = "SYSTEM_TABLE_NAME"
os.environ["HLS_HS256_API_AUTH_SECRET_KEY_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["CLOUDFRONT_COOKIE_PRIVATE_KEY_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["CLOUDFRONT_COOKIE_KEY_PAIR_ID_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["CLOUDFRONT_DOMAIN_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["HLS_STREAM_CLOUDFRONT_DISTRO"] = "SYSTEM_TABLE_NAME"
os.environ["HLS_STREAMING_SIGNED_URL_EXPIRATION_HRS"] = "SYSTEM_TABLE_NAME"
os.environ["CURRENT_EVENTS_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["PROGRAM_EVENT_PLUGIN_INDEX"] = "PROGRAM_EVENT_PLUGIN_INDEX"
os.environ["PROMPT_CATALOG_TABLE_NAME"] = "PROMPT_CATALOG_TABLE_NAME"
os.environ["PROMPT_CATALOG_NAME_INDEX"] = "PROMPT_CATALOG_NAME_INDEX"
os.environ["PROMPT_CATALOG_VERSION_INDEX"] = "PROMPT_CATALOG_VERSION_INDEX"
os.environ["AWS_ACCESS_KEY_ID"] = "AWS_ACCESS_KEY_ID"
os.environ["AWS_SECRET_ACCESS_KEY"] = "AWS_SECRET_ACCESS_KEY"
os.environ["OS_VECTORSEARCH_COLLECTION_EP"] = "OS_VECTORSEARCH_COLLECTION_EP"


os.environ["FRAME_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["CHUNK_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["CHUNK_STARTPTS_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["PLUGIN_RESULT_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["CLIP_PREVIEW_FEEDBACK_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["EB_EVENT_BUS_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["REPLAY_RESULT_TABLE_NAME"] = "SYSTEM_TABLE_NAME"
os.environ["PROGRAM_EVENT_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_TRACK_INDEX"] = "SYSTEM_TABLE_NAME"
os.environ["CLIP_PREVIEW_FEEDBACK_PROGRAM_EVENT_CLASSIFIER_START_INDEX"] = (
    "SYSTEM_TABLE_NAME"
)
os.environ["SERVICE_DISC_SERVICE_ID"] = "SERVICE_DISC_SERVICE_ID"
os.environ["API_AUTH_SECRET_KEY_NAME"] = "API_AUTH_SECRET_KEY_NAME"
os.environ["TRIGGER_LAMBDA_ARN"] = "TRIGGER_LAMBDA_ARN"
os.environ["JOB_TRACKER_TABLE_NAME"] = "JOB_TRACKER_TABLE_NAME"

os.environ["PLUGIN_URL"] = "PLUGIN_URL"
os.environ["SYSTEM_URL"] = "SYSTEM_URL"
os.environ["PROFILE_URL"] = "SYSTEM_URL"
os.environ["MODEL_URL"] = "SYSTEM_URL"
os.environ["PROMPT_CATALOG_URL"] = "SYSTEM_URL"
os.environ["EVENT_URL"] = "SYSTEM_URL"
os.environ["CONTENT_GROUP_URL"] = "SYSTEM_URL"
os.environ["PROGRAM_URL"] = "SYSTEM_URL"
os.environ["WORKFLOW_URL"] = "SYSTEM_URL"
os.environ["REPLAY_URL"] = "SYSTEM_URL"
os.environ["EVENT_PROGRAM_INDEX"] = "EVENT_PROGRAM_INDEX"
os.environ["TRANSITION_CLIP_S3_BUCKET"] = "TRANSITION_CLIP_S3_BUCKET"
os.environ["TRANSITIONS_CONFIG_TABLE_NAME"] = "TRANSITIONS_CONFIG_TABLE_NAME"
os.environ["PARTITION_KEY_CHUNK_NUMBER_INDEX"] = "PARTITION_KEY_CHUNK_NUMBER_INDEX"
os.environ["PARTITION_KEY_END_INDEX"] = "PARTITION_KEY_END_INDEX"
os.environ["MAX_DETECTOR_QUERY_WINDOW_SECS"] = "10"
os.environ["PROGRAM_EVENT_LABEL_INDEX"] = "PROGRAM_EVENT_LABEL_INDEX"
os.environ["NON_OPTO_SEGMENTS_INDEX"] = "NON_OPTO_SEGMENTS_INDEX"
os.environ["EVENT_BYOB_NAME_INDEX"] = "EVENT_BYOB_NAME_INDEX"
os.environ["EB_SCHEDULE_ROLE_ARN"] = "EB_SCHEDULE_ROLE_ARN"
os.environ["MEDIA_OUTPUT_BUCKET_NAME"] = "MEDIA_OUTPUT_BUCKET_NAME"
os.environ["EB_EVENT_BUS_ARN"] = "EB_EVENT_BUS_ARN"
os.environ["CUSTOM_PRIORITIES_URL"] = "CUSTOM_PRIORITIES_URL"
os.environ["CUSTOM_PRIORITIES_TABLE_NAME"] = "CUSTOM_PRIORITIES_TABLE_NAME"
os.environ["MEDIALIVE_ACCESS_ROLE"] = "MEDIALIVE_ACCESS_ROLE"
os.environ["MRE_JWT_ISSUER"] = "MRE_JWT_ISSUER"
os.environ["MRE_HSA_API_AUTH_SECRET"] = "MRE_HSA_API_AUTH_SECRET"