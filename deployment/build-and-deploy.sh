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

parse_params "$@"
msg "Build parameters:"
msg "- Version: ${version}"
msg "- Region: ${region}"
msg "- Profile: ${profile}"
msg "- Build AWS Lambda layers? $(if [[ -z $NO_LAYER ]]; then echo 'True'; else echo 'False'; fi)"
msg "- Deploy Frontend? $(if [[ -z $NO_GUI ]]; then echo 'True'; else echo 'False'; fi)"
msg "- Enable SSM Parameter Store high throughput setting? $(if [[ ! -z $HIGH_THROUGHPUT ]]; then echo 'True'; else echo 'False'; fi)"

echo ""
sleep 3

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
  # Check if git is installed
  if [[ ! -x "$(command -v git)" ]]; then
    echo "ERROR: Command not found: git"
    echo "ERROR: This script requires git to be installed"
    echo "ERROR: Please install it and rerun this script"
    exit 1
  fi

  # Get the email address to send login credentials for the UI
  echo "Please insert your email address to receive credentials required for the UI login:"
  read ADMIN_EMAIL
fi

# Get reference for all important folders
build_dir="$PWD"
source_dir="$build_dir/../source"
control_plane_dir="$source_dir"/controlplaneapi
data_plane_dir="$source_dir"/dataplaneapi
frontend_dir="$source_dir"/frontend
lambda_layers_dir="$control_plane_dir/infrastructure/lambda_layers"

# Create and activate a temporary Python environment for this script
echo "------------------------------------------------------------------------------"
echo "Creating a temporary Python virtualenv for this script"
echo "------------------------------------------------------------------------------"
command -v python3 > /dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: install Python3 before running this script"
    exit 1
fi
python3 -c "import os; print (os.getenv('VIRTUAL_ENV'))" | grep -q None
if [ $? -ne 0 ]; then
    echo "ERROR: Do not run this script inside Virtualenv. Type \`deactivate\` and run again.";
    exit 1;
fi
echo "Using python virtual environment:"
VENV=$(mktemp -d) && echo "$VENV"
python3 -m venv "$VENV"
source "$VENV"/bin/activate
pip3 install wheel
pip3 install -q urllib3 requests requests-aws4auth
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install required Python libraries to build the helper packages."
    exit 1
fi
export PYTHONPATH="$PYTHONPATH:$source_dir/lib/MediaReplayEnginePluginHelper/:$source_dir/lib/MediaReplayEngineWorkflowHelper/"

echo "------------------------------------------------------------------------------"
echo "Building MediaReplayEnginePluginHelper package"
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
echo "Building MediaReplayEngineWorkflowHelper package"
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
  if `./build-lambda-layer.sh > /dev/null`; then
    mv MediaReplayEnginePluginHelper.zip "$lambda_layers_dir"/MediaReplayEnginePluginHelper/
    mv MediaReplayEngineWorkflowHelper.zip "$lambda_layers_dir"/MediaReplayEngineWorkflowHelper/
    mv timecode.zip "$lambda_layers_dir"/timecode/
    mv ffmpeg.zip "$lambda_layers_dir"/ffmpeg/
    mv ffprobe.zip "$lambda_layers_dir"/ffprobe/
    rm -rf MediaReplayEnginePluginHelper/ MediaReplayEngineWorkflowHelper/ timecode/ ffmpeg/ ffprobe/
    echo "Lambda layer build script completed.";
  else
    echo "ERROR: Failed to build Lambda layers using docker"
    exit 1
  fi
  cd "$build_dir" || exit 1
fi

echo "------------------------------------------------------------------------------"
echo "Updating Framework version to $version"
echo "------------------------------------------------------------------------------"
# Update the CDK stack in place
sed -i -e "s/%%FRAMEWORK_VERSION%%/$version/" "$control_plane_dir/infrastructure/stacks/chaliceapp.py"

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
echo "Controlplane API stack"
echo "------------------------------------------------------------------------------"

echo "Building Controlplane stack"
cd "$control_plane_dir" || exit 1

# Remove cdk.out and chalice deployments in the CDK project to force redeploy when there are changes to configuration
[ -e cdk.out ] && rm -rf cdk.out
[ -e infrastructure/cdk.out ] && rm -rf infrastructure/cdk.out
[ -e infrastructure/chalice.out ] && rm -rf infrastructure/chalice.out
[ -e runtime/.chalice/deployments ] && rm -rf runtime/.chalice/deployments

echo "Installing Python dependencies"
pip3 install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install required Python dependencies for the Controlplane stack."
    exit 1
fi
echo "Deploying the Controlplane stack"
cd "$control_plane_dir"/infrastructure
cdk deploy --require-approval never $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to deploy the Controlplane stack."
    exit 1
fi
control_plane=true
echo "Finished deploying the Controlplane stack"

echo "------------------------------------------------------------------------------"
echo "Dataplane API stack"
echo "------------------------------------------------------------------------------"

echo "Building Dataplane stack"
cd "$data_plane_dir" || exit 1

# Remove cdk.out and chalice deployments in the CDK project to force redeploy when there are changes to configuration
[ -e cdk.out ] && rm -rf cdk.out
[ -e infrastructure/cdk.out ] && rm -rf infrastructure/cdk.out
[ -e infrastructure/chalice.out ] && rm -rf infrastructure/chalice.out
[ -e runtime/.chalice/deployments ] && rm -rf runtime/.chalice/deployments

echo "Installing Python dependencies"
pip3 install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install required Python dependencies for the Dataplane stack."
    exit 1
fi
echo "Deploying the Dataplane stack"
cd "$data_plane_dir"/infrastructure
cdk deploy --require-approval never $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to deploy the Dataplane stack."
    if [ ! -z $control_plane ]; then
      echo "Destroying the Controlplane stack"
      cd "$control_plane_dir"/infrastructure
      cdk destroy $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
    fi
    exit 1
fi
echo "Finished deploying the Dataplane stack"

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
  pip3 install -q -r requirements.txt
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

  echo "Updating Amplify environment variables and custom headers based on the CDK output"
  (python3 init-amplify.py $region $(if [ ! -z $profile ]; then echo "$profile"; fi)) 2>&1

  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to update Amplify environment variables and custom headers."
      exit 1
  fi

  echo "Pushing the code to CodeCommit for Amplify deployment"

  cd "$frontend_dir" || exit 1
  git clone "codecommit::$region://$(if [ ! -z $profile ]; then echo "$profile@"; fi)mre-frontend"
  rsync -r --exclude 'mre-frontend' --exclude 'node_modules' --exclude 'cdk' . mre-frontend
  cd "$frontend_dir"/mre-frontend
  # git config user.name mre-frontend-user
  # git config user.email $ADMIN_EMAIL
  git add .
  git commit -m "Initial commit"
  git push
  rm -rf "$frontend_dir"/mre-frontend
  
  echo "------------------------------------------------------------------------------"
  echo "Successfully deployed the Frontend stack"
  echo ""
  echo "NOTE: Amplify will take a few minutes to provision, build, and deploy the     "
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