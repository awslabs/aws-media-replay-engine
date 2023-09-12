
#!/bin/bash

###############################################################################
# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
# PURPOSE:
#   Deploys MRE Regression test suites
#   PROFILE needs to be in a format like us-east-1
# USAGE:
#  ./deploy.sh --profile {PROFILE}
#    PROFILE is optional. The ~/.aws/credentials profile that you would like to use
#
###############################################################################


usage() {
  msg "$msg"
  cat <<EOF
Usage: $(basename "${BASH_SOURCE[0]}") --profile PROFILE

Available options:

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


  return 0
}

parse_params "$@"
msg "Test Suite parameters:"
msg "- Profile: ${profile}"

echo ""
sleep 3



echo "------------------------------------------------------------------------------"
echo "Creating and activating Python virtual environment"
echo "------------------------------------------------------------------------------"

python3 -m venv .env
source .env/bin/activate
python3 -m pip install -r requirements.txt


echo "------------------------------------------------------------------------------"
echo "Deploying MRE test suite ..."
echo "------------------------------------------------------------------------------"

cd Infrastructure
cdk deploy  $(if [ ! -z $profile ]; then echo "--profile $profile"; fi)
deactivate
echo "Deploying MRE test suite ... done"