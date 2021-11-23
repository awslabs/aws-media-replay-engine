#!/bin/bash
###############################################################################
# DO NOT MODIFY THIS FILE.
###############################################################################
#
# This assumes all of the OS-level configuration has been completed and git repo has already been cloned
#
# This script should be run from the repo's deployment directory
# cd deployment
# ./build-open-source-dist.sh solution-name
#
# Paramenters:
#  - solution-name: name of the solution for consistency

# Check to see if input has been provided:
if [ -z "$1" ]; then
    echo "Please provide the trademark approved solution name for the open source package."
    echo "For example: ./build-open-source-dist.sh trademarked-solution-name"
    exit 1
fi

# Get reference for all important folders
orig_deployment_dir="$PWD"
orig_source_dir="$orig_deployment_dir/../source"
dist_dir="$orig_deployment_dir/open-source/"$1""
dist_deployment_dir="$dist_dir/deployment"
dist_source_dir="$dist_dir/source"

echo "------------------------------------------------------------------------------"
echo "[Init] Clean old open-source folder"
echo "------------------------------------------------------------------------------"
echo 'rm -rf "$orig_deployment_dir"/open-source/'
rm -rf "$orig_deployment_dir"/open-source/
echo 'rm -rf "$dist_dir"'
rm -rf "$dist_dir"
echo 'mkdir -p "$dist_dir"'
mkdir -p "$dist_dir"
echo 'mkdir -p "$dist_deployment_dir"'
mkdir -p "$dist_deployment_dir"
echo 'mkdir -p "$dist_source_dir"'
mkdir -p "$dist_source_dir"

echo "------------------------------------------------------------------------------"
echo "[Packing] Build Script"
echo "------------------------------------------------------------------------------"
echo 'cp "$orig_deployment_dir"/build-and-deploy.sh "$dist_deployment_dir"'
cp "$orig_deployment_dir"/build-and-deploy.sh "$dist_deployment_dir"
echo 'cp -R "$orig_deployment_dir"/lambda_layer_factory "$dist_deployment_dir"'
cp -R "$orig_deployment_dir"/lambda_layer_factory "$dist_deployment_dir"

echo "------------------------------------------------------------------------------"
echo "[Packing] Source Folder"
echo "------------------------------------------------------------------------------"
echo 'cp -R "$orig_source_dir"/* "$dist_source_dir"/'
cp -R "$orig_source_dir"/* "$dist_source_dir"/

echo "------------------------------------------------------------------------------"
echo "[Packing] Documentation"
echo "------------------------------------------------------------------------------"
echo "cp -R $orig_deployment_dir/../docs $dist_dir"
cp -R $orig_deployment_dir/../docs $dist_dir
echo "cp $orig_deployment_dir/../LICENSE $dist_dir"
cp $orig_deployment_dir/../LICENSE $dist_dir
echo "cp $orig_deployment_dir/../NOTICE $dist_dir"
cp $orig_deployment_dir/../NOTICE $dist_dir
echo "cp $orig_deployment_dir/../README.md $dist_dir"
cp $orig_deployment_dir/../README.md $dist_dir
echo "cp $orig_deployment_dir/../CODE_OF_CONDUCT.md $dist_dir"
cp $orig_deployment_dir/../CODE_OF_CONDUCT.md $dist_dir
echo "cp $orig_deployment_dir/../CONTRIBUTING.md $dist_dir"
cp $orig_deployment_dir/../CONTRIBUTING.md $dist_dir

echo "------------------------------------------------------------------------------"
echo "[Packing] Remove compiled python and node.js files"
echo "------------------------------------------------------------------------------"
echo "find $dist_dir -iname "dist" -type d -exec rm -rf "{}" \; 2> /dev/null"
find $dist_dir -iname "dist" -type d -exec rm -rf "{}" \; 2> /dev/null
echo "find $dist_dir -iname "package" -type d -exec rm -rf "{}" \; 2> /dev/null"
find $dist_dir -iname "package" -type d -exec rm -rf "{}" \; 2> /dev/null
echo "find $dist_dir -iname "__pycache__" -type d -exec rm -rf "{}" \; 2> /dev/null"
find $dist_dir -iname "__pycache__" -type d -exec rm -rf "{}" \; 2> /dev/null
echo "find $dist_dir -iname "cdk.out" -type d -exec rm -rf "{}" \; 2> /dev/null"
find $dist_dir -iname "cdk.out" -type d -exec rm -rf "{}" \; 2> /dev/null
echo "find $dist_dir -iname "chalice.out" -type d -exec rm -rf "{}" \; 2> /dev/null"
find $dist_dir -iname "chalice.out" -type d -exec rm -rf "{}" \; 2> /dev/null
echo "find $dist_dir -iname "node_modules" -type d -exec rm -rf "{}" \; 2> /dev/null"
find $dist_dir -iname "node_modules" -type d -exec rm -rf "{}" \; 2> /dev/null
echo "find $dist_dir -iname "deployments" -type d -exec rm -rf "{}" \; 2> /dev/null"
find $dist_dir -iname "deployments" -type d -exec rm -rf "{}" \; 2> /dev/null
echo "find $dist_dir -type f -name 'package-lock.json' -delete"
find $dist_dir -type f -name 'package-lock.json' -delete

echo "------------------------------------------------------------------------------"
echo "[Packing] Clean library and lambda layer folders"
echo "------------------------------------------------------------------------------"
echo 'rm -rf "$dist_source_dir"/frontend/build'
rm -rf "$dist_source_dir"/frontend/build
echo 'rm -rf "$dist_source_dir"/lib/MediaReplayEnginePluginHelper/build'
rm -rf "$dist_source_dir"/lib/MediaReplayEnginePluginHelper/build
echo 'rm -rf "$dist_source_dir"/lib/MediaReplayEnginePluginHelper/Media_Replay_Engine_Plugin_Helper*.egg-info'
rm -rf "$dist_source_dir"/lib/MediaReplayEnginePluginHelper/Media_Replay_Engine_Plugin_Helper*.egg-info
echo 'rm -rf "$dist_source_dir"/lib/MediaReplayEngineWorkflowHelper/build'
rm -rf "$dist_source_dir"/lib/MediaReplayEngineWorkflowHelper/build
echo 'rm -rf "$dist_source_dir"/lib/MediaReplayEngineWorkflowHelper/Media_Replay_Engine_Workflow_Helper*.egg-info'
rm -rf "$dist_source_dir"/lib/MediaReplayEngineWorkflowHelper/Media_Replay_Engine_Workflow_Helper*.egg-info

echo 'rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/ffmpeg/ffmpeg*.zip'
rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/ffmpeg/ffmpeg*.zip
echo 'rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/ffprobe/ffprobe*.zip'
rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/ffprobe/ffprobe*.zip
echo 'rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/timecode/timecode*.zip'
rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/timecode/timecode*.zip
echo 'rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/MediaReplayEnginePluginHelper/MediaReplayEnginePluginHelper*.zip'
rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/MediaReplayEnginePluginHelper/MediaReplayEnginePluginHelper*.zip
echo 'rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/MediaReplayEngineWorkflowHelper/MediaReplayEngineWorkflowHelper*.zip'
rm -rf "$dist_source_dir"/controlplaneapi/infrastructure/lambda_layers/MediaReplayEngineWorkflowHelper/MediaReplayEngineWorkflowHelper*.zip

echo 'rm -f "$dist_deployment_dir"/lambda_layer_factory/ffmpeg*'
rm -f "$dist_deployment_dir"/lambda_layer_factory/ffmpeg*
echo 'rm -f "$dist_deployment_dir"/lambda_layer_factory/ffprobe*'
rm -f "$dist_deployment_dir"/lambda_layer_factory/ffprobe*
echo 'rm -f "$dist_deployment_dir"/lambda_layer_factory/timecode*'
rm -f "$dist_deployment_dir"/lambda_layer_factory/timecode*
echo 'rm -f "$dist_deployment_dir"/lambda_layer_factory/Media_Replay_Engine*.whl'
rm -f "$dist_deployment_dir"/lambda_layer_factory/Media_Replay_Engine*.whl
echo 'rm -rf "$dist_deployment_dir"/lambda_layer_factory/MediaReplayEnginePluginHelper*'
rm -rf "$dist_deployment_dir"/lambda_layer_factory/MediaReplayEnginePluginHelper*
echo 'rm -rf "$dist_deployment_dir"/lambda_layer_factory/MediaReplayEngineWorkflowHelper*'
rm -rf "$dist_deployment_dir"/lambda_layer_factory/MediaReplayEngineWorkflowHelper*

echo "------------------------------------------------------------------------------"
echo "[Packing] Create GitHub (open-source) zip file"
echo "------------------------------------------------------------------------------"
echo "cd $dist_dir"
cd $dist_dir/../
echo "zip -q -r9 ./$1.zip $1"
zip -q -r9 ./"$1".zip "$1"
echo "Clean up open-source folder"
echo "rm -rf $1"
rm -rf "$1"
echo "Completed building $1.zip dist"