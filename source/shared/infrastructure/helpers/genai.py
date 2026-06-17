#  Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

_TRUTHY_VALUES = ("1", "true", "yes", "on")


def is_generative_ai_enabled(node) -> bool:
    """Strict parser for the GENERATIVE_AI CDK context flag.

    `node.try_get_context("GENERATIVE_AI")` returns a non-empty string
    (e.g. "false") when callers pass `-c GENERATIVE_AI=false`, which is
    truthy in Python and silently enables GenAI features. Use this helper
    everywhere the flag is consumed so that only explicit truthy spellings
    enable the feature.
    """
    raw = node.try_get_context("GENERATIVE_AI")
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in _TRUTHY_VALUES
