#!/bin/bash
###############################################################################
# PURPOSE: Build Lambda layer for user-specified Python libraries using docker.
#
# PREREQUISITES:
#   docker
#
# USAGE:
#   ./build-lambda-layer.sh
#
###############################################################################

# Check to see if Docker is installed
docker --version
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

echo "------------------------------------------------------------------------------"
echo "Building Lambda Layer zip files"
echo "------------------------------------------------------------------------------"
rm -rf ./MediaReplayEnginePluginHelper/
rm -rf ./MediaReplayEngineWorkflowHelper/
rm -rf ./timecode/
rm -rf ./ffmpeg/
rm -rf ./ffprobe/
rm -f ./MediaReplayEnginePluginHelper.zip
rm -f ./MediaReplayEngineWorkflowHelper.zip
rm -f ./timecode.zip
rm -f ./ffmpeg.zip
rm -f ./ffprobe.zip

docker build --tag=lambda_layer_factory:latest --platform linux/amd64 . 2>&1 > /dev/null 

if [ $? -eq 0 ]; then
  # Check the operating system
  if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
      docker run --rm -it -v /${PWD}:/packages lambda_layer_factory
  else
      docker run --rm -it -v "$PWD":/packages lambda_layer_factory
  fi
  
fi
if [[ ! -f ./MediaReplayEnginePluginHelper.zip ]] || [[ ! -f ./MediaReplayEngineWorkflowHelper.zip ]] || [[ ! -f ./timecode.zip ]] || [[ ! -f ./ffmpeg.zip ]] || [[ ! -f ./ffprobe.zip ]]; then
    echo "ERROR: Failed to build lambda layer zip file."
    exit 1
fi

echo "------------------------------------------------------------------------------"
echo "Verifying whether all the Lambda layers meet AWS size limits"
echo "------------------------------------------------------------------------------"
# See https://docs.aws.amazon.com/lambda/latest/dg/limits.html
unzip -q -d MediaReplayEnginePluginHelper ./MediaReplayEnginePluginHelper.zip
unzip -q -d MediaReplayEngineWorkflowHelper ./MediaReplayEngineWorkflowHelper.zip
unzip -q -d timecode ./timecode.zip
unzip -q -d ffmpeg ./ffmpeg.zip
unzip -q -d ffprobe ./ffprobe.zip
ZIPPED_LIMIT=50
UNZIPPED_LIMIT=250
UNZIPPED_SIZE_MRE_PH=$(du -sm ./MediaReplayEnginePluginHelper/ | cut -f 1)
ZIPPED_SIZE_MRE_PH=$(du -sm ./MediaReplayEnginePluginHelper.zip | cut -f 1)
UNZIPPED_SIZE_MRE_WH=$(du -sm ./MediaReplayEngineWorkflowHelper/ | cut -f 1)
ZIPPED_SIZE_MRE_WH=$(du -sm ./MediaReplayEngineWorkflowHelper.zip | cut -f 1)
UNZIPPED_SIZE_TC=$(du -sm ./timecode/ | cut -f 1)
ZIPPED_SIZE_TC=$(du -sm ./timecode.zip | cut -f 1)
UNZIPPED_SIZE_FFM=$(du -sm ./ffmpeg/ | cut -f 1)
ZIPPED_SIZE_FFM=$(du -sm ./ffmpeg.zip | cut -f 1)
UNZIPPED_SIZE_FFP=$(du -sm ./ffprobe/ | cut -f 1)
ZIPPED_SIZE_FFP=$(du -sm ./ffprobe.zip | cut -f 1)
rm -rf ./MediaReplayEnginePluginHelper/
rm -rf ./MediaReplayEngineWorkflowHelper/
rm -rf ./timecode/
rm -rf ./ffmpeg/
rm -rf ./ffprobe/
if (( $UNZIPPED_SIZE_MRE_PH > $UNZIPPED_LIMIT || $ZIPPED_SIZE_MRE_PH > $ZIPPED_LIMIT || $UNZIPPED_SIZE_MRE_WH > $UNZIPPED_LIMIT || $ZIPPED_SIZE_MRE_WH > $ZIPPED_LIMIT || $UNZIPPED_SIZE_TC > $UNZIPPED_LIMIT || $ZIPPED_SIZE_TC > $ZIPPED_LIMIT || $UNZIPPED_SIZE_FFM > $UNZIPPED_LIMIT || $ZIPPED_SIZE_FFM > $ZIPPED_LIMIT || $UNZIPPED_SIZE_FFP > $UNZIPPED_LIMIT || $ZIPPED_SIZE_FFP > $ZIPPED_LIMIT )); then
  echo "ERROR: Lambda layer package exceeds AWS size limits.";
  exit 1
fi

echo "Lambda layers have been saved to the lambda_layer_factory directory."

echo "------------------------------------------------------------------------------"
echo "Done"
echo "------------------------------------------------------------------------------"
