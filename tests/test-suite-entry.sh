
#!/bin/bash

###############################################################################
# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
# PURPOSE:
#   Executes MRE Regression test suites
#    REGION needs to be in a format like us-east-1
#    PROFILE is optional. The ~/.aws/credentials profile that you would like to use
# USAGE:
#  ./build-and-deploy.sh --region {REGION}
#    REGION needs to be in a format like us-east-1
#
###############################################################################


usage() {
  msg "$msg"
  cat <<EOF
Usage: $(basename "${BASH_SOURCE[0]}") --region REGION --profile PROFILE

Available options:

--region    AWS Region, formatted like us-east-1
--profile   AWS profile for CLI commands (optional)

EOF
  exit 1
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
    --region)
      region="${2}"
      shift
      ;;
    --profile)
      profile="${2:-default}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${region}" ]] && usage "Missing required parameter: region"

  return 0
}

parse_params "$@"
msg "Test Suite parameters:"
msg "- Region: ${region}"
msg "- Profile: ${profile}"

echo ""
sleep 3

export PYTHONPATH=.

echo "------------------------------------------------------------------------------"
echo "Creating and activating Python virtual environment"
echo "------------------------------------------------------------------------------"

python3 -m venv .env
source .env/bin/activate
python3 -m pip install -r requirements.txt


echo "------------------------------------------------------------------------------"
echo "Getting AWS Creds and setting Env Variables ..."
echo "------------------------------------------------------------------------------"

account_id=$(aws sts get-caller-identity --query Account ${profile:+--profile $profile} --output text)
if [ $? -ne 0 ]; then
  msg "ERROR: Unable to retrieve AWS caller identity, credentials are invalid."
  die 1
fi

echo "Getting AWS Creds and setting Env Variables ...done"

# Skip setting explicit credentials when running on EC2 - will use instance profile credentials
if [ ! -z "${profile}" ] && [ "${profile}" != "default" ]; then
    
    export AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id --profile $profile)
    export AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key --profile $profile)
    export AWS_SESSION_TOKEN=$(aws configure get aws_session_token --profile $profile)
else
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600") \
    && CREDENTIALS=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/iam/security-credentials/$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/)) \
    && export AWS_ACCESS_KEY_ID=$(echo $CREDENTIALS | jq -r '.AccessKeyId') \
    && export AWS_SECRET_ACCESS_KEY=$(echo $CREDENTIALS | jq -r '.SecretAccessKey') \
    && export AWS_SESSION_TOKEN=$(echo $CREDENTIALS | jq -r '.Token')
fi
export AWS_ACCOUNT_ID=$account_id
export AWS_REGION=$region
export AWS_DEFAULT_REGION=$region


echo $AWS_ACCOUNT_ID
echo $AWS_REGION
echo $AWS_DEFAULT_REGION


# Model, plugin and profile Tests
############################################# MODELS TESTS #######################################################################
pytest -s -v ./core/Models/models_test.py --self-contained-html --html=models_test.html

############################################# PLUGIN TESTS #######################################################################
pytest -s -v ./core/Plugins/plugin_test.py --self-contained-html --html=plugin_test.html

############################################# PROFILE TESTS #######################################################################
pytest -s -v ./core/Profiles/profiles_test.py --self-contained-html --html=profiles_test.html

############################################# EVENT TESTS #######################################################################
# MediaLive VOD Events 
pytest -s -v -m past_event_media_live_as_source ./core/Events/event_media_live_test.py -n 1 --self-contained-html --html=past_event_media_live_as_source.html

pytest -s -v -m past_event_media_live_as_source_thumbnails_control ./core/Events/event_media_live_test.py -n 4 --self-contained-html --html=past_event_media_live_as_source_thumbnails.html

# MediaLive VOD Events with No Optimizer in Profile
pytest -s -v -m past_event_media_live_as_source_without_optimizer ./core/Events/event_media_live_test.py -n 1 --self-contained-html --html=past_event_media_live_as_source_without_optimizer.html

# # MediaLive FUTURE Events 
pytest -s -v -m future_event_media_live_as_source ./core/Events/event_media_live_test.py -n 4 --self-contained-html --html=future_event_media_live_as_source.html

# # MediaLive FUTURE Events with No Optimizer in Profile
pytest -s -v -m future_event_media_live_as_source_without_optimizer ./core/Events/event_media_live_test.py -n 1 --self-contained-html --html=future_event_media_live_as_source_without_optimizer.html

# # BYOB VOD Events
pytest -s -v -m past_event_byob_as_source ./core/Events/event_byob_test.py -n 4 --self-contained-html --html=past_event_byob_as_source.html

# # BYOB VOD Events with No Optimizer in Profile
pytest -s -v -m past_event_byob_as_source_without_optimizer ./core/Events/event_byob_test.py -n 1 --self-contained-html --html=past_event_byob_as_source_without_optimizer.html

# # BYOB FUTURE Events 
pytest -s -v -m future_event_byob_as_source ./core/Events/event_byob_test.py -n 4 --self-contained-html --html=future_event_byob_as_source.html

# # BYOB FUTURE Events with No Optimizer in Profile
pytest -s -v -m future_event_byob_as_source_without_optimizer ./core/Events/event_byob_test.py -n 1 --self-contained-html --html=future_event_byob_as_source_without_optimizer.html

############################################# REPLAY TESTS #######################################################################

deactivate