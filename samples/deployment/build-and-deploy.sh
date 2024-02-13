#!/bin/bash
###############################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# PURPOSE:
#   Build and deploy CloudFormation templates for the sample applications using AWS CDK.
#
# USAGE:
#  ./build-and-deploy.sh [-h] [-v] --app {APPLICATION} --region {REGION} --profile {PROFILE}
#    APPLICATION needs to be one of the following values: plugin-samples, model-samples, fan-experience-frontend, hls-harvester-sample
#    REGION needs to be in a format like us-east-1
#    PROFILE is optional. It's the profile that you have setup in ~/.aws/credentials
#      that you want to use for the AWS CLI and CDK commands.
#
#    The following options are available:
#
#     -h | --help                     Print usage
#     -v | --verbose                  Print script debug info
#
###############################################################################

trap cleanup_and_die SIGINT SIGTERM ERR

usage() {
  msg "$msg"
  cat <<EOF
Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [--profile PROFILE] --app APPLICATION --region REGION
Available options:
-h, --help                      Print this help and exit (optional)
-v, --verbose                   Print script debug info (optional)
--app                           One of the following MRE Sample applications to deploy: plugin-samples, model-samples, fan-experience-frontend, hls-harvester-sample
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
    --app)
      app="${2}"
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
  [[ -z "${app}" ]] && usage "Missing required parameter: app"
  [[ -z "${region}" ]] && usage "Missing required parameter: region"

  return 0
}

parse_params "$@"
msg "Build parameters:"
msg "- Application: ${app}"
msg "- Region: ${region}"
msg "- Profile: ${profile}"

echo ""
sleep 3

# Check if a valid application name is given
if ! [[ "$app" =~ ^(plugin-samples|model-samples|fan-experience-frontend|hls-harvester-sample)$ ]]; then
  echo "ERROR: Invalid application name: $app. Should be one of the following: plugin-samples, model-samples, fan-experience-frontend, hls-harvester-sample"
  echo "ERROR: Please rerun this script with the correct application name"
  exit 1
fi

# Verify Python min version
resp="$(python3 -c 'import sys; print("Valid Version" if sys.version_info.major == 3 and sys.version_info.minor == 11 else "Invalid Version")')"
if [[ $resp =~ "Invalid Version" ]]; then
  echo "ERROR: Invalid Python version:"
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

# Check if region is supported by MRE
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
   echo "ERROR: $region region is not supported by MRE"
   exit 1
fi

# Set the AWS_DEFAULT_REGION env variable
export AWS_DEFAULT_REGION=$region

# Check if MRE is already deployed in the region
aws ssm get-parameter --name " /MRE/ControlPlane/EndpointURL" $(if [ ! -z $profile ]; then echo "--profile $profile"; fi) > /dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Could not find MRE in $region region. Please install it from https://github.com/awslabs/aws-media-replay-engine"
    exit 1
fi

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

if [ "$app" = "plugin-samples" ]; then
  # Get reference for all important folders
  build_dir="$PWD"
  source_dir="$build_dir/../source"
  plugin_samples_dir="$source_dir/mre-plugin-samples"

  echo "------------------------------------------------------------------------------"
  echo "Plugin Samples stack"
  echo "------------------------------------------------------------------------------"

  cd "$plugin_samples_dir/cdk" || exit 1

  # Remove cdk.out and cdk-outputs.json in the CDK project to force redeploy when there are changes to configuration
  [ -e cdk.out ] && rm -rf cdk.out
  [ -e stacks/cdk.out ] && rm -rf stacks/cdk.out
  [ -e cdk-outputs.json ] && rm -rf cdk-outputs.json

  echo "Installing Python dependencies"
  pip3 install -q -r requirements.txt
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to install required Python dependencies for the Plugins stack."
      exit 1
  fi

  echo "Getting the latest MediaReplayEnginePluginHelper layer version arn"
  helper_layer_arn=$(aws lambda list-layer-versions --layer-name MediaReplayEnginePluginHelper --query "LayerVersions[0].LayerVersionArn" $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
  if [ $? -ne 0 ]; then
      msg "ERROR: Failed to get the latest MediaReplayEnginePluginHelper layer version arn"
      die 1
  fi

  # Remove leading and trailing double-quotes in helper layer arn
  helper_layer_arn=$(sed -e 's/^"//' -e 's/"$//' <<< $helper_layer_arn)
  pip install --target "$source_dir"/custom-resource/package -r "$source_dir"/custom-resource/requirements.txt --upgrade --no-user
  cp "$source_dir"/custom-resource/handler.py "$source_dir"/custom-resource/package


#  Download mre helper layer zip and add to the dockerfile for DockerImage lambda deployment
  echo "Downloading the MediaReplayEnginePluginHelper layer for docker build"

  for d in ../Plugins/*/; do
    if ! test -f "${d}Dockerfile"; then
        rm -rf ${d}package
        FILE=${d}requirements.txt
        if test -f "$FILE"; then
            echo "$FILE exists. Running pip install"
            pip install --target ${d}package -r ${d}requirements.txt --upgrade
        else
            echo "$FILE does not exist. No pip install needed"
            mkdir -p ${d}package
        fi
        # copy all the lambda function files into /package for deployment
        cp "${d}"*.py ${d}package/
        cp "${d}"*.json ${d}package/
        cp "${d}"*.md ${d}package/

        # Verify Lambda Layer size See https://docs.aws.amazon.com/lambda/latest/dg/limits.html
        ZIPPED_LIMIT=50
        UNZIPPED_LIMIT=250
        UNZIPPED_SIZE_MRE_PH=$(du -sm "${d}package/" | cut -f 1)
        if (( $UNZIPPED_SIZE_MRE_PH > $UNZIPPED_LIMIT)) ; then
          echo "ERROR: Lambda layer package exceeds AWS size limits.";
          exit 1
        fi
    else
        rm -rf ${d}mre_plugin_helper
        rm -rf ${d}mre_plugin_helper.zip
        echo "Dockerfile found - skipping packaging"

        # download mre_helper_layer to include in Lambda docker deployment
        URL=$(aws lambda get-layer-version-by-arn --arn $helper_layer_arn --query Content.Location --output text $(if [ ! -z $profile ]; then echo "--profile $profile"; fi))
        curl -s -o "${d}mre_plugin_helper.zip" "$URL"
        unzip -qq "${d}mre_plugin_helper.zip" -d "${d}mre_plugin_helper/"
    fi
  done

  echo "Deploying the Plugins stack"
  cdk deploy --require-approval never --outputs-file ./cdk-outputs.json --parameters helperlayerarn=$helper_layer_arn $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to deploy the Plugins stack."
      exit 1
  fi
  echo "Finished deploying the Plugins stack and successfully registered the plugins"

  echo "------------------------------------------------------------------------------"
  echo "Successfully deployed the plugin-samples application"
  echo "------------------------------------------------------------------------------"


  # clean up build environment
  for d in "${plugin_samples_dir}"/Plugins/*/; do
    rm -rf ${d}mre_plugin_helper
    rm -rf ${d}mre_plugin_helper.zip
  done

fi

if [ "$app" = "fan-experience-frontend" ]; then
  # Get the email address to send login credentials for the UI
  echo "Please insert your email address to receive credentials required for the UI login:"
  read ADMIN_EMAIL

  # Get reference for all important folders
  build_dir="$PWD"
  source_dir="$build_dir/../source"
  fan_experience_dir="$source_dir/mre-fan-experience-frontend"

  echo "------------------------------------------------------------------------------"
  echo "Fan Experience Frontend stack"
  echo "------------------------------------------------------------------------------"

  cd "$fan_experience_dir/cdk" || exit 1

  # Remove cdk.out and cdk-outputs.json in the CDK project to force redeploy when there are changes to configuration
  [ -e cdk.out ] && rm -rf cdk.out
  [ -e stacks/cdk.out ] && rm -rf stacks/cdk.out
  [ -e cdk-outputs.json ] && rm -rf cdk-outputs.json

  echo "Installing Python dependencies"
  pip3 install -q -r requirements.txt
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to install required Python dependencies for the Fan Experience Frontend stack."
      exit 1
  fi

  echo "Deploying the Fan Experience Frontend stack"
  cdk deploy --require-approval never --outputs-file ./cdk-outputs.json --parameters adminemail=$ADMIN_EMAIL $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to deploy the Fan Experience Frontend stack."
      exit 1
  fi
  echo "Finished deploying the Fan Experience Frontend stack"

  echo "Updating Amplify environment variables and custom headers based on the CDK output"
  (python3 init-amplify.py $region $(if [ ! -z $profile ]; then echo "$profile"; fi)) 2>&1

  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to update Amplify environment variables and custom headers."
      exit 1
  fi

  echo "Pushing the code to CodeCommit for Amplify deployment"

  cd "$fan_experience_dir" || exit 1
  git clone "codecommit::$region://$(if [ ! -z $profile ]; then echo "$profile@"; fi)mre-fan-experience-frontend"
  rsync -r --exclude 'mre-fan-experience-frontend' --exclude 'node_modules' --exclude 'cdk' . mre-fan-experience-frontend
  cd "$fan_experience_dir"/mre-fan-experience-frontend
  git checkout -b master
  # git config user.name mre-fan-experience-user
  # git config user.email $ADMIN_EMAIL
  git add .
  git commit -m "Initial commit"
  git push --set-upstream origin master
  rm -rf "$fan_experience_dir"/mre-fan-experience-frontend

  echo "-------------------------------------------------------------------------------"
  echo "Successfully deployed the fan-experience-frontend application"
  echo ""
  echo "NOTE: Amplify will take a few minutes to provision, build, and deploy the Fan  "
  echo "Experience Frontend application. Please monitor the progress in the AWS Amplify"
  echo "console under 'mre-fan-experience-frontend' application. Once deployed, click  "
  echo "on the URL within the application and login using the credentials sent to your "
  echo "email address.                                                                 "
  echo "-------------------------------------------------------------------------------"
fi

if [ "$app" = "hls-harvester-sample" ]; then
  # Get reference for all important folders
  build_dir="$PWD"
  source_dir="$build_dir/../source"
  video_ingestion_dir="$source_dir/mre-video-ingestion-samples"
  hls_harvester_dir="$video_ingestion_dir/HLS_Harvester"

  echo "------------------------------------------------------------------------------"
  echo "HLS Harvester Video Ingestion Sample stack"
  echo "------------------------------------------------------------------------------"

  cd "$hls_harvester_dir" || exit 1

  # Remove cdk.out and cdk-outputs.json in the CDK project to force redeploy when there are changes to configuration
  [ -e cdk.out ] && rm -rf cdk.out
  [ -e infrastructure/cdk.out ] && rm -rf infrastructure/cdk.out
  [ -e infrastructure/chalice.out ] && rm -rf infrastructure/chalice.out
  [ -e runtime/.chalice/deployments ] && rm -rf runtime/.chalice/deployments

  echo "Installing Python dependencies"
  pip3 install -q -r requirements.txt
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to install required Python dependencies for the HLS Harvester Sample stack."
      exit 1
  fi

  echo "Deploying the HLS Harvester Sample stack"
  cd "$hls_harvester_dir"/infrastructure
  cdk deploy --require-approval never $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
  if [ $? -ne 0 ]; then
      echo "ERROR: Failed to deploy the HLS Harvester Sample stack."
      exit 1
  fi
  echo "Finished deploying the HLS Harvester Sample stack"

  echo "------------------------------------------------------------------------------"
  echo "Successfully deployed the hls-harvester-sample application"
  echo "------------------------------------------------------------------------------"
fi

cleanup
exit 0
