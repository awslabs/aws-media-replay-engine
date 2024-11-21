#!/bin/bash
###############################################################################
# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
###############################################################################
# Tested Environment Configuration:
# Amazon Linux 2023 (AML2023)
# Architecture: x86_64
# Instance Type: t2.large (uses about 60% of CPU)
# EBS Storage: 16 GB gp3
###############################################################################

###############################################################################
# Prerequisites Installation Section
# This section installs and configures all required software packages
###############################################################################

# Create the installation status file if it doesn't exist
INSTALLATION_STATUS_FILE="/home/ec2-user/.env-init"
sudo touch $INSTALLATION_STATUS_FILE

# Update system packages
echo "Updating system packages..."
sudo dnf update -y
echo "System packages update status: $?" >> $INSTALLATION_STATUS_FILE

# Install and configure Python 3.11
echo "Installing Python 3.11 and dependencies..."
sudo dnf install python3.11 python3.11-pip -y
echo "Python 3.11 installation status: $?" >> $INSTALLATION_STATUS_FILE
echo "Configuring Python 3.11 as default Python version..."

echo "Installing Python virtual environment package..."
python3.11 -m pip install --user virtualenv
echo "Python virtualenv installation status: $?" >> $INSTALLATION_STATUS_FILE

# Install AWS CLI
echo "Installing AWS Command Line Interface..."
sudo dnf install awscli -y
echo "AWS CLI installation status: $?" >> $INSTALLATION_STATUS_FILE

# Install and configure Docker
echo "Installing Docker Engine..." 
sudo dnf install docker -y
echo "Docker installation status: $?" >> $INSTALLATION_STATUS_FILE
echo "Configuring Docker permissions..."
sudo usermod -aG docker ec2-user
newgrp docker
echo "Docker permissions configuration status: $?" >> $INSTALLATION_STATUS_FILE
echo "Starting Docker service..."
sudo service docker start
echo "Docker service start status: $?" >> $INSTALLATION_STATUS_FILE

# Install Node.js runtime
echo "Installing Node.js 20.x runtime..."
curl -sL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install nodejs -y
echo "Node.js installation status: $?" >> $INSTALLATION_STATUS_FILE

# Install Node Package Manager
echo "Installing latest NPM version..."
sudo npm install -g npm@latest
echo "NPM installation status: $?" >> $INSTALLATION_STATUS_FILE

# Install AWS Cloud Development Kit
echo "Installing AWS CDK framework..."
sudo npm install -g aws-cdk@latest
echo "AWS CDK installation status: $?" >> $INSTALLATION_STATUS_FILE

# Install version control
echo "Installing Git version control..."
sudo dnf install git -y
echo "Git installation status: $?" >> $INSTALLATION_STATUS_FILE


###############################################################################
# MRE (Media Replay Engine) Installation Section
# This section sets up the MRE deployment environment and dependencies
###############################################################################

# Set deployment configuration variables
ADMIN_EMAIL="" # Required: Set your admin email address
MRE_DEPLOYMENT_DIR="/home/ec2-user/mredeploy"

# Example command to get AWS region (uncomment to deploy in same region as instance)
# REGION=$(aws configure get region)

# Initialize MRE deployment environment
echo "Initializing MRE deployment environment..."
mkdir -p $MRE_DEPLOYMENT_DIR
cd $MRE_DEPLOYMENT_DIR
echo "Working directory: $(pwd)"

# Clone MRE repository
# echo "Cloning Media Replay Engine repository..."
# git clone https://github.com/awslabs/aws-media-replay-engine.git
# cd aws-media-replay-engine/deployment

# Configure Python virtual environment
echo "Configuring Python virtual environment..."
cd $MRE_DEPLOYMENT_DIR
python3.11 -m venv mredeploy-env

# Example deployment command (uncomment and configure as needed):
# Before running deployment:
# 1. Make sure ADMIN_EMAIL is set above
# 2. Ensure you are in the correct AWS region
# 3. The virtual environment must be activated first
# source mredeploy-env/bin/activate
# Then run the deployment script with required parameters:
# ./build-and-deploy.sh --version 1.0 --region $REGION --admin-email $ADMIN_EMAIL
# Monitor the CloudFormation console for deployment progress
