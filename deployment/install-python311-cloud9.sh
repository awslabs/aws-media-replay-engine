#!/bin/bash
###############################################################################
# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
# PURPOSE: Install python3.11 on a Cloud9 instance
#
# PREREQUISITES:
#   This script should be run on a Cloud9 Instance using the Amazon Linux 2 AMI
#
# USAGE:
#   ./install-python311-cloud9.sh
#

# Update and install development tools
yum update -y
yum groupinstall -y "Development Tools"
yum remove -y openssl openssl-devel
yum install -y \
    autoconf \
    automake \
    bzip2 \
    bzip2-devel \
    cmake \
    freetype-devel \
    gcc \
    gcc-c++ \
    git \
    libtool \
    make \
    mercurial \
    pkgconfig \
    zlib-devel \
    openssl11 \
    openssl11-devel \
    libffi-devel \
    wget \
    tar \
    gzip \
    zip

# Install Python 3.11
cd /
wget https://www.python.org/ftp/python/3.11.5/Python-3.11.5.tgz
tar -xzf Python-3.11.5.tgz
cd /Python-3.11.5
./configure --enable-optimizations
make install
ln -sf /usr/local/bin/python3.11 /usr/bin/python3 