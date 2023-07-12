#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Media Replay Engine Plugin Helper",
    version="1.0.0",
    author="Aravindharaj Rajendran",
    author_email="redacted@example.com",
    description="Helper library to aid the development of custom plugins for the Media Replay Engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/awslabs/aws-media-replay-engine",
    packages=setuptools.find_packages(),
    install_requires=[
        'urllib3<2',
        'requests',
        'requests-aws4auth'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
)
