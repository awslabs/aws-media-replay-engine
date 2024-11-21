#!/bin/bash
###############################################################################
# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
# PURPOSE:
#   Build and deploy CloudFormation templates for the Media Replay Engine using AWS CDK.
#
# USAGE:
#  ./build-and-deploy.sh [-h] [-v] [--no-layer] [--disable-ui] [--enable-ssm-high-throughput] --version {VERSION} --region {REGION} --profile {PROFILE}
#    VERSION should be in a format like 1.0.0
#    REGION needs to be in a format like us-east-1
#    PROFILE is optional. It's the profile that you have setup in ~/.aws/credentials
#      that you want to use for the AWS CLI and CDK commands.
#
#    The following options are available:
#
#     -h | --help                     Print usage
#     -v | --verbose                  Print script debug info
#     --no-layer                      Do not build AWS Lambda layers
#     --disable-ui                    Do not deploy the Frontend
#     --enable-ssm-high-throughput    Increase SSM Parameter Store throughput
#
###############################################################################

trap cleanup_and_die SIGINT SIGTERM ERR

usage() {
  msg "$msg"
  cat <<EOF
Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [--no-layer] [--disable-ui] [--enable-ssm-high-throughput] [--profile PROFILE] --version VERSION --region REGION

Available options:

-h, --help                      Print this help and exit (optional)
-v, --verbose                   Print script debug info (optional)
--no-layer                      Do not build AWS Lambda layers (optional)
--disable-ui                    Do not deploy the Frontend (optional)
--enable-ssm-high-throughput    Increase SSM Parameter Store throughput (optional)
--version                       Arbitrary string indicating framework version
--region                        AWS Region, formatted like us-east-1
--profile                       AWS profile for CLI commands (optional)
EOF
  exit 1
}

cleanup_and_die() {
  trap - SIGINT SIGTERM ERR
  echo "Trapped signal."
  cleanup
  die 1
}

cleanup() {
  # Deactivate and remove the temporary python virtualenv used to run this script
  if [[ "$VIRTUAL_ENV" != "" ]];
  then
    deactivate
    cd "$build_dir"/ || exit 1
    echo "Deleting python virtual environment $VENV"
    rm -rf "$VENV"
    echo "------------------------------------------------------------------------------"
    echo "Clean up complete"
    echo "------------------------------------------------------------------------------"
  fi
}

msg() {
  echo >&2 -e "${1-}"
}

die() {
  local msg=$1
  local code=${2-1} # default exit status 1
  msg "$msg"
  exit "$code"
}

parse_params() {
  # default values of variables set from params
  flag=0
  param=''

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    --no-layer) NO_LAYER=1 ;;
    --disable-ui) NO_GUI=1 ;;
    --enable-ssm-high-throughput) HIGH_THROUGHPUT=1 ;;
    --admin-email)
      ADMIN_EMAIL="${2}"
      shift
      ;;
    --version)
      version="${2}"
      shift
      ;;
    --region)
      region="${2}"
      shift
      ;;
    --profile)
      profile="${2}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${version}" ]] && usage "Missing required parameter: version"
  [[ -z "${region}" ]] && usage "Missing required parameter: region"

  return 0
}

deploy_cdk_app() {
  stack_name=$1
  stack_dir=$2
  is_header=${3:-true}

  if [ "$is_header" = true ]; then
    echo "------------------------------------------------------------------------------"
    echo "$stack_name stack"
    echo "------------------------------------------------------------------------------"
  fi

  echo "Building the $stack_name stack"
  cd "$stack_dir" || exit 1

  # Remove cdk.out and chalice deployments in the CDK project to force redeploy when there are changes to configuration
  [ -e cdk.out ] && rm -rf cdk.out
  [ -e infrastructure/cdk.out ] && rm -rf infrastructure/cdk.out
  [ -e infrastructure/chalice.out ] && rm -rf infrastructure/chalice.out
  [ -e runtime/.chalice/deployments ] && rm -rf runtime/.chalice/deployments

  echo "Installing Python dependencies"
  pip3 install -U -q -r requirements.txt
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to install required Python dependencies for the $stack_name stack."
      exit 1
  fi
  echo "Deploying the $stack_name stack"
  cd "$stack_dir"/infrastructure
  cdk deploy --require-approval never $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
      echo "ERROR: Failed to deploy the $stack_name stack."
      exit 1
  fi
  echo "Finished deploying the $stack_name stack"
}

parse_params "$@"
msg "Build parameters:"
msg "- Version: ${version}"
msg "- Region: ${region}"
msg "- Profile: ${profile}"
msg "- Admin Email: ${ADMIN_EMAIL}"
msg "- Build AWS Lambda layers? $(if [[ -z $NO_LAYER ]]; then echo 'True'; else echo 'False'; fi)"
msg "- Deploy Frontend? $(if [[ -z $NO_GUI ]]; then echo 'True'; else echo 'False'; fi)"
msg "- Enable SSM Parameter Store high throughput setting? $(if [[ ! -z $HIGH_THROUGHPUT ]]; then echo 'True'; else echo 'False'; fi)"

echo ""
sleep 3

# Verify Python min version
resp="$(python3 -c 'import sys; print("Valid Version" if sys.version_info.major == 3 and sys.version_info.minor == 11 else f"Invalid Version {sys.version_info.major}.{sys.version_info.minor}")')"
if [[ $resp =~ "Invalid Version" ]]; then
  echo "ERROR: $resp"
  echo "ERROR: Required version: 3.11"
  echo "ERROR: Please install it and rerun this script"
  exit 1
fi


# Check if aws is installed
if [[ ! -x "$(command -v aws)" ]]; then
  echo "ERROR: Command not found: aws"
  echo "ERROR: This script requires the AWS CLI to be installed and configured"
  echo "ERROR: Please install it and rerun this script"
  exit 1
fi

# Check if cdk is installed
if [[ ! -x "$(command -v cdk)" ]]; then
  echo "ERROR: Command not found: cdk"
  echo "ERROR: This script requires the AWS CDK to be installed"
  echo "ERROR: Please install it and rerun this script. Refer: https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html#getting_started_install"
  exit 1
fi

# Check if Docker is installed and running
if [[ -z $NO_LAYER ]]; then
  docker --version > /dev/null
  if [ $? -ne 0 ]; then
    echo "ERROR: install Docker before running this script"
    exit 1
  else
    docker ps > /dev/null
    if [ $? -ne 0 ]; then
        echo "ERROR: start Docker before running this script"
        exit 1
    fi
  fi
fi

# Check if region is supported by MediaConvert
if [ "$region" != "us-east-1" ] &&
   [ "$region" != "us-east-2" ] &&
   [ "$region" != "us-west-1" ] &&
   [ "$region" != "us-west-2" ] &&
   [ "$region" != "eu-west-1" ] &&
   [ "$region" != "eu-west-2" ] &&
   [ "$region" != "eu-west-3" ] &&
   [ "$region" != "eu-central-1" ] &&
   [ "$region" != "eu-north-1" ] &&
   [ "$region" != "ap-south-1" ] &&
   [ "$region" != "ap-northeast-1" ] &&
   [ "$region" != "ap-southeast-1" ] &&
   [ "$region" != "ap-southeast-2" ] &&
   [ "$region" != "ap-northeast-2" ] &&
   [ "$region" != "ca-central-1" ] &&
   [ "$region" != "sa-east-1" ]; then
   echo "ERROR: AWS Elemental MediaConvert operations are not supported in $region region"
   exit 1
fi

# Set the AWS_DEFAULT_REGION env variable
export AWS_DEFAULT_REGION=$region

if [[ -z $NO_GUI ]]; then
  # Check if npm is installed
  if [[ ! -x "$(command -v npm)" ]]; then
    echo "ERROR: Command not found: npm"
    echo "ERROR: This script requires git to be installed"
    echo "ERROR: Please install it and rerun this script"
    exit 1
  fi

  # Get the email address to send login credentials for the UI
  if [[ -z $ADMIN_EMAIL ]]; then
    echo "Please insert your email address to receive credentials required for the UI login:"
    read ADMIN_EMAIL
  fi
fi

# Set architecture for Docker usage
export DOCKER_DEFAULT_PLATFORM=linux/amd64

# Get reference for all important folders
build_dir="$PWD"
source_dir="$build_dir/../source"
api_dir="$source_dir/api"
gateway_dir="$source_dir/gateway"
backend_dir="$source_dir/backend"
frontend_dir="$source_dir/frontend"
lambda_layers_dir="$source_dir/layers"
shared_dir="$source_dir/shared"

# Create and activate a temporary Python environment for this script
echo "------------------------------------------------------------------------------"
echo "Creating a temporary Python virtualenv for this script"
echo "------------------------------------------------------------------------------"
echo "Using python virtual environment:"
VENV=$(mktemp -d) && echo "$VENV"
python3 -m venv "$VENV"
# Check the operating system
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    source "$VENV"/Scripts/activate
else
    source "$VENV"/bin/activate
fi
pip3 install wheel
pip3 install -q urllib3 requests requests-aws4auth
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install required Python libraries to build the helper packages."
    exit 1
fi
export PYTHONPATH="$PYTHONPATH:$source_dir/lib/MediaReplayEnginePluginHelper/:$source_dir/lib/MediaReplayEngineWorkflowHelper/"

echo "------------------------------------------------------------------------------"
echo "Validating MediaReplayEnginePluginHelper package"
echo "------------------------------------------------------------------------------"

cd "$source_dir"/lib/MediaReplayEnginePluginHelper || exit 1
rm -rf build
rm -rf dist
rm -rf Media_Replay_Engine_Plugin_Helper.egg-info
python3 setup.py bdist_wheel > /dev/null
echo -n "Created: "
find "$source_dir"/lib/MediaReplayEnginePluginHelper/dist/
cd "$build_dir"/ || exit 1

echo "------------------------------------------------------------------------------"
echo "Validating MediaReplayEngineWorkflowHelper package"
echo "------------------------------------------------------------------------------"

cd "$source_dir"/lib/MediaReplayEngineWorkflowHelper || exit 1
rm -rf build
rm -rf dist
rm -rf Media_Replay_Engine_Workflow_Helper.egg-info
python3 setup.py bdist_wheel > /dev/null
echo -n "Created: "
find "$source_dir"/lib/MediaReplayEngineWorkflowHelper/dist/
cd "$build_dir"/ || exit 1

if [[ ! -z "${NO_LAYER}" ]]; then
  echo "------------------------------------------------------------------------------"
  echo "Skipping the process to build Lambda layers due to --no-layer option"
  echo "------------------------------------------------------------------------------"
else
  echo "------------------------------------------------------------------------------"
  echo "Building Lambda Layers"
  echo "------------------------------------------------------------------------------"
  cd "$build_dir"/lambda_layer_factory/ || exit 1

  rm -f MediaReplayEnginePluginHelper.zip*
  rm -f MediaReplayEngineWorkflowHelper.zip*
  rm -f timecode.zip*
  rm -f ffmpeg.zip*
  rm -f ffprobe.zip*
  rm -f Media_Replay_Engine*.whl

  # Build MediaReplayEnginePluginHelper library
  cp -R "$source_dir"/lib/MediaReplayEnginePluginHelper .
  cd MediaReplayEnginePluginHelper/ || exit 1
  echo "Building MediaReplayEnginePluginHelper python library"
  python3 setup.py bdist_wheel > /dev/null
  cp dist/*.whl ../
  cp dist/*.whl "$source_dir"/lib/MediaReplayEnginePluginHelper/dist/
  echo "MediaReplayEnginePluginHelper python library is at $source_dir/lib/MediaReplayEnginePluginHelper/dist/"
  cd "$source_dir"/lib/MediaReplayEnginePluginHelper/dist/ || exit 1
  ls -1 "$(pwd)"/*.whl
  if [ $? -ne 0 ]; then
    echo "ERROR: Failed to build MediaReplayEnginePluginHelper python library"
    exit 1
  fi
  cd "$build_dir"/lambda_layer_factory/ || exit 1
  rm -rf MediaReplayEnginePluginHelper/
  file=$(ls Media_Replay_Engine_Plugin_Helper*.whl)
  # Note, $(pwd) will be mapped to /packages/ in the Docker container used for building the Lambda zip files. We reference /packages/ in requirements.txt for that reason.
  # Add the whl file to requirements.txt if it is not already there
  rm -f requirements.txt
  echo "/packages/$file" >> requirements.txt

  # Build MediaReplayEngineWorkflowHelper library
  cp -R "$source_dir"/lib/MediaReplayEngineWorkflowHelper .
  cd MediaReplayEngineWorkflowHelper/ || exit 1
  echo "Building MediaReplayEngineWorkflowHelper python library"
  python3 setup.py bdist_wheel > /dev/null
  cp dist/*.whl ../
  cp dist/*.whl "$source_dir"/lib/MediaReplayEngineWorkflowHelper/dist/
  echo "MediaReplayEngineWorkflowHelper python library is at $source_dir/lib/MediaReplayEngineWorkflowHelper/dist/"
  cd "$source_dir"/lib/MediaReplayEngineWorkflowHelper/dist/ || exit 1
  ls -1 "$(pwd)"/*.whl
  if [ $? -ne 0 ]; then
    echo "ERROR: Failed to build MediaReplayEngineWorkflowHelper python library"
    exit 1
  fi
  cd "$build_dir"/lambda_layer_factory/ || exit 1
  rm -rf MediaReplayEngineWorkflowHelper/
  file=$(ls Media_Replay_Engine_Workflow_Helper*.whl)
  # Note, $(pwd) will be mapped to /packages/ in the Docker container used for building the Lambda zip files. We reference /packages/ in requirements.txt for that reason.
  # Add the whl file to requirements.txt if it is not already there
  echo "/packages/$file" >> requirements.txt

  # Build Lambda layer zip files and move them to the AWS CDK ControlPlane stack. The Lambda layer build script runs in Docker.
  rm -rf "$lambda_layers_dir"/MediaReplayEnginePluginHelper/MediaReplayEnginePluginHelper*.zip
  rm -rf "$lambda_layers_dir"/MediaReplayEngineWorkflowHelper/MediaReplayEngineWorkflowHelper*.zip
  rm -rf "$lambda_layers_dir"/timecode/timecode*.zip
  rm -rf "$lambda_layers_dir"/ffmpeg/ffmpeg*.zip
  rm -rf "$lambda_layers_dir"/ffprobe/ffprobe*.zip
  echo "Running build-lambda-layer.sh to build Lambda layers using docker:"
  rm -rf MediaReplayEngine*.zip timecode.zip ffmpeg.zip ffprobe.zip
  ./build-lambda-layer.sh 2>&1 | tee build-lambda-layer.log
  if [ $? -eq 0 ]; then
    mv MediaReplayEnginePluginHelper.zip "$lambda_layers_dir"/MediaReplayEnginePluginHelper/
    mv MediaReplayEngineWorkflowHelper.zip "$lambda_layers_dir"/MediaReplayEngineWorkflowHelper/
    mv timecode.zip "$lambda_layers_dir"/timecode/
    mv ffmpeg.zip "$lambda_layers_dir"/ffmpeg/
    mv ffprobe.zip "$lambda_layers_dir"/ffprobe/
    rm -rf MediaReplayEnginePluginHelper/ MediaReplayEngineWorkflowHelper/ timecode/ ffmpeg/ ffprobe/
    echo "Lambda layer build script completed.";
  else
    echo "ERROR: Failed to build Lambda layers using docker"
    echo "ERROR: Check build-lambda-layer.log for details"
    exit 1
  fi
  cd "$build_dir" || exit 1
fi

echo "------------------------------------------------------------------------------"
echo "Bootstrapping CDK"
echo "------------------------------------------------------------------------------"
# Get account id
account_id=$(aws sts get-caller-identity --query Account --output text $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
if [ $? -ne 0 ]; then
  msg "ERROR: Failed to get AWS account ID"
  die 1
fi
cdk bootstrap aws://$account_id/$region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)

echo "------------------------------------------------------------------------------"
echo "Updating Framework version to $version"
echo "------------------------------------------------------------------------------"
# Update in place
sed -i -e "s/%%FRAMEWORK_VERSION%%/$version/" "$shared_dir/infrastructure/helpers/constants.py"

# Gracefully unblock CloudFormation cross-stack export references due to Python version upgrade in MRE v2.9.0
# Applicable only when upgrading from MRE v2.x.x to v2.9.0 or later
echo "------------------------------------------------------------------------------"
echo "Unblocking CloudFormation cross-stack export references"
echo "------------------------------------------------------------------------------"
# Check if MRE is already deployed in the region
controlplane_endpoint_param=$(aws ssm describe-parameters --output text --parameter-filters "Key=Name,Values=/MRE/ControlPlane/EndpointURL" --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
if [[ -z "${controlplane_endpoint_param}" ]]; then
  echo "No unblocking needed as an existing version of MRE is not found in $region region"
else
  workflow_layer_param=$(aws ssm describe-parameters --output text --parameter-filters "Key=Name,Values=/MRE/WorkflowHelperLambdaLayerArn" --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
  if [[ -z "${workflow_layer_param}" ]]; then
    echo "Proceeding with the unblocking operation as the existing version of MRE found in $region region is earlier than v2.9.0"
    echo "Getting the latest timecode layer version arn"
    timecode_layer_arn=$(aws lambda list-layer-versions --output text --layer-name aws_mre_timecode --query "LayerVersions[0].LayerVersionArn" --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
    if [ $? -ne 0 ]; then
        msg "ERROR: Failed to get the latest timecode layer version arn"
        die 1
    fi
    echo "Getting the latest ffmpeg layer version arn"
    ffmpeg_layer_arn=$(aws lambda list-layer-versions --output text --layer-name aws_mre_ffmpeg --query "LayerVersions[0].LayerVersionArn" --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
    if [ $? -ne 0 ]; then
        msg "ERROR: Failed to get the latest ffmpeg layer version arn"
        die 1
    fi
    echo "Getting the latest ffprobe layer version arn"
    ffprobe_layer_arn=$(aws lambda list-layer-versions --output text --layer-name aws_mre_ffprobe --query "LayerVersions[0].LayerVersionArn" --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
    if [ $? -ne 0 ]; then
        msg "ERROR: Failed to get the latest ffprobe layer version arn"
        die 1
    fi
    echo "Getting the latest MediaReplayEngineWorkflowHelper layer version arn"
    workflow_helper_layer_arn=$(aws lambda list-layer-versions --output text --layer-name MediaReplayEngineWorkflowHelper --query "LayerVersions[0].LayerVersionArn" --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
    if [ $? -ne 0 ]; then
        msg "ERROR: Failed to get the latest MediaReplayEngineWorkflowHelper layer version arn"
        die 1
    fi
    echo "Getting the latest MediaReplayEnginePluginHelper layer version arn"
    plugin_helper_layer_arn=$(aws lambda list-layer-versions --output text --layer-name MediaReplayEnginePluginHelper --query "LayerVersions[0].LayerVersionArn" --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
    if [ $? -ne 0 ]; then
        msg "ERROR: Failed to get the latest MediaReplayEnginePluginHelper layer version arn"
        die 1
    fi
    echo "Getting the system dynamodb table arn from CloudFormation outputs"
    system_table_arn=$(aws cloudformation describe-stacks --output text --stack-name aws-mre-shared-resources --query "Stacks[0].Outputs[?OutputKey=='mresystemtablearn'].OutputValue" --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
    if [ $? -ne 0 ]; then
        msg "ERROR: Failed to get the system dynamodb table arn from CloudFormation outputs"
        die 1
    fi
    system_table_name=$(echo "$system_table_arn" | cut -d/ -f2)

    # Create SSM parameters with the retrieved arns
    aws ssm put-parameter --name "/MRE/TimecodeLambdaLayerArn" --value $timecode_layer_arn --type String --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
    aws ssm put-parameter --name "/MRE/FfmpegLambdaLayerArn" --value $ffmpeg_layer_arn --type String --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
    aws ssm put-parameter --name "/MRE/FfprobeLambdaLayerArn" --value $ffprobe_layer_arn --type String --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
    aws ssm put-parameter --name "/MRE/WorkflowHelperLambdaLayerArn" --value $workflow_helper_layer_arn --type String --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
    aws ssm put-parameter --name "/MRE/PluginHelperLambdaLayerArn" --value $plugin_helper_layer_arn --type String --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
    aws ssm put-parameter --name "/MRE/ControlPlane/SystemTableArn" --value $system_table_arn --type String --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
    aws ssm put-parameter --name "/MRE/ControlPlane/SystemTableName" --value $system_table_name --type String --region $region $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)

    # Deploy all the cross-stacks where the export references are found
    # Segment Caching stack
    deploy_cdk_app "Segment Caching" "$backend_dir/caching"

    # Clip Generation stack
    deploy_cdk_app "Clip Generation" "$backend_dir/clipgeneration"

    # Data Export stack
    deploy_cdk_app "Data Export" "$backend_dir/data_export"

    # Event Life Cycle Handler stack
    deploy_cdk_app "Event Life Cycle Handler" "$backend_dir/event-life-cycle"

    # Replay Handler stack
    deploy_cdk_app "Replay Handler" "$backend_dir/replay"

    # Workflow Trigger stack
    deploy_cdk_app "Workflow Trigger" "$backend_dir/workflow_trigger"

    # System stack
    deploy_cdk_app "System" "$api_dir/controlplane/system"

    # Profile stack
    deploy_cdk_app "Profile" "$api_dir/controlplane/profile"

    # Delete SSM parameters created earlier
    aws ssm delete-parameters --names "/MRE/TimecodeLambdaLayerArn" "/MRE/FfmpegLambdaLayerArn" "/MRE/FfprobeLambdaLayerArn" "/MRE/WorkflowHelperLambdaLayerArn" "/MRE/PluginHelperLambdaLayerArn" "/MRE/ControlPlane/SystemTableArn" "/MRE/ControlPlane/SystemTableName" $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)

    # Wait for 30 seconds for the delete propagation
    sleep 30
  else
    echo "No unblocking needed as the existing version of MRE found in $region region is v2.9.0 or later"
  fi
fi

echo "------------------------------------------------------------------------------"
echo "Shared Resources stack"
echo "------------------------------------------------------------------------------"
deploy_cdk_app "Shared Resources" "$shared_dir" false

echo "------------------------------------------------------------------------------"
echo "Backend stacks"
echo "------------------------------------------------------------------------------"
# Segment Caching stack
deploy_cdk_app "Segment Caching" "$backend_dir/caching"

# Clip Generation stack
deploy_cdk_app "Clip Generation" "$backend_dir/clipgeneration"

# Data Export stack
deploy_cdk_app "Data Export" "$backend_dir/data_export"

# Event Life Cycle Handler stack
deploy_cdk_app "Event Life Cycle Handler" "$backend_dir/event-life-cycle"

# Replay Handler stack
deploy_cdk_app "Replay Handler" "$backend_dir/replay"

# Workflow Trigger stack
deploy_cdk_app "Workflow Trigger" "$backend_dir/workflow_trigger"

echo "------------------------------------------------------------------------------"
echo "Controlplane API stacks"
echo "------------------------------------------------------------------------------"
# Program stack
deploy_cdk_app "Program" "$api_dir/controlplane/program"

# ContentGroup stack
deploy_cdk_app "ContentGroup" "$api_dir/controlplane/contentgroup"

# System stack
deploy_cdk_app "System" "$api_dir/controlplane/system"

# Model stack
deploy_cdk_app "Model" "$api_dir/controlplane/model"

# Plugin stack
deploy_cdk_app "Plugin" "$api_dir/controlplane/plugin"

# Profile stack
deploy_cdk_app "Profile" "$api_dir/controlplane/profile"

# Workflow stack
deploy_cdk_app "Workflow" "$api_dir/controlplane/workflow"

# Event stack
deploy_cdk_app "Event" "$api_dir/controlplane/event"

# Replay stack
deploy_cdk_app "Replay" "$api_dir/controlplane/replay"

# Custom Priorities stack
deploy_cdk_app "CustomPriorities" "$api_dir/controlplane/custompriorities"

echo "------------------------------------------------------------------------------"
echo "Dataplane API stack"
echo "------------------------------------------------------------------------------"
deploy_cdk_app "Dataplane API" "$api_dir/dataplane" false

echo "------------------------------------------------------------------------------"
echo "Gateway API stack"
echo "------------------------------------------------------------------------------"
deploy_cdk_app "Gateway API" "$gateway_dir" false

if [[ ! -z "${NO_GUI}" ]]; then
  echo "------------------------------------------------------------------------------"
  echo "Skipping the build and deployment of Frontend due to --disable-ui option"
  echo "------------------------------------------------------------------------------"
else
  echo "------------------------------------------------------------------------------"
  echo "Building and Deploying the Frontend stack"
  echo "------------------------------------------------------------------------------"

  cd "$frontend_dir" || exit 1

  # Remove cdk.out and cdk-outputs.json in the CDK project to force redeploy when there are changes to configuration
  [ -e cdk.out ] && rm -rf cdk.out
  [ -e cdk/cdk.out ] && rm -rf cdk/cdk.out
  [ -e cdk/cdk-outputs.json ] && rm -rf cdk/cdk-outputs.json

  cd "$frontend_dir"/cdk
  echo "Installing Python dependencies"
  pip3 install -U -q -r requirements.txt
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to install required Python dependencies for the Frontend stack."
      exit 1
  fi
  echo "Deploying the Frontend stack"
  cdk deploy --require-approval never $(if [ ! -z $profile ]; then echo "--profile $profile"; fi) --outputs-file ./cdk-outputs.json --parameters adminemail=$ADMIN_EMAIL
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to deploy the Frontend stack."
      exit 1
  fi
  echo "Finished deploying the Frontend stack"

  echo "Creating env file for frontend deployment"
  mode="New"
  (python3 create-env-file.py $region $mode $(if [ ! -z $profile ]; then echo "$profile"; fi)) 2>&1

  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to create necessary env file"
      exit 1
  fi

  cd "$frontend_dir"
  echo "Building the Frontend"
  npm i --legacy-peer-deps
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to install dependencies for the Frontend."
      exit 1
  fi
  npm run build
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to build the Frontend."
      exit 1
  fi

  cd "$frontend_dir"/build
  zip -r -q -X ./build.zip *

  cd "$frontend_dir"/cdk
  echo "Updating Amplify environment variables and custom headers based on the CDK output"
  mode="New"
  (python3 init-amplify.py $region $mode $(if [ ! -z $profile ]; then echo "$profile"; fi)) 2>&1

  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to update Amplify environment variables and custom headers."
      exit 1
  fi

  ## Cleanup build dir
  cd "$frontend_dir"
  [ -e build ] && rm -rf build
  [ -e .env ] && rm -rf .env
  
  echo "------------------------------------------------------------------------------"
  echo "Successfully deployed the Frontend stack"
  echo ""
  echo "NOTE: Amplify will take a few seconds to deploy the     "
  echo "Frontend application. Please monitor the progress in the AWS Amplify console  "
  echo "under 'mre-frontend' application. Once deployed, click on the URL within the  "
  echo "application and login using the credentials sent to your email address.       "
  echo "------------------------------------------------------------------------------"
fi

# Enable SSM Parameter Store high throughput setting if required
if [ ! -z $HIGH_THROUGHPUT ]; then
    echo "Enabling SSM Parameter Store high throughput setting for '$region' in account '$account_id'"
    aws ssm update-service-setting --setting-id "arn:aws:ssm:$region:$account_id:servicesetting/ssm/parameter-store/high-throughput-enabled" --setting-value "true" $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
    if [ $? -ne 0 ]; then
      msg "ERROR: Failed to enable SSM Parameter Store high throughput setting"
      msg "ERROR: Please enable it manually - https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-store-throughput.html"
    fi
fi

cleanup
echo "------------------------------------------------------------------------------"
echo "Successfully deployed the MRE Framework"
echo "------------------------------------------------------------------------------"
exit 0