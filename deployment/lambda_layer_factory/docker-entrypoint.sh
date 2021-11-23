#!/bin/bash

echo "================================================================================"
echo "Building and installing FFMpeg and FFProbe from source"
echo "================================================================================"
ROOT_DIR="/packages/ffmpeg-sources"
BD_PREFIX="$ROOT_DIR"
BD_BIN="$ROOT_DIR/bin"
BD_LIB="$ROOT_DIR/lib"

FFMPEG_VERSION="n4.4.1"

function buildNASM() {
  local version="2.15.05"
  local package="nasm-$version.tar.bz2"

  echo "== Building NASM $version =="

  curl -q -O -L https://www.nasm.us/pub/nasm/releasebuilds/$version/$package
  [ $? -ne 0 ] && \
    onFailure "failed to download NASM code"

  tar xjf $package
  [ $? -ne 0 ] && \
    onFailure "failed to untar '$package'"

  pushd nasm-$version
  ./autogen.sh && \
  ./configure --prefix="$BD_PREFIX" --bindir="$BD_BIN" && \
  make && make install
  [ $? -ne 0 ] && \
    onFailure "failed to build NASM code"
  popd

  echo "== Completed building NASM $version =="
  return 0
}

function buildYASM() {
  local version="1.3.0"
  local package="yasm-$version.tar.gz"

  echo "== Building YASM $version =="

  curl -q -O -L https://www.tortall.net/projects/yasm/releases/$package
  [ $? -ne 0 ] && \
    onFailure "failed to download YASM code"

  tar xzf $package
  [ $? -ne 0 ] && \
    onFailure "failed to untar '$package'"

  pushd yasm-$version
  ./configure --prefix="$BD_PREFIX" --bindir="$BD_BIN" && \
  make && \
  make install
  [ $? -ne 0 ] && \
    onFailure "failed to build YASM code"
  popd

  echo "== Completed building YASM $version =="
  return 0
}

function buildFFMpeg() {
  local version="$FFMPEG_VERSION"
  local package="$version.tar.gz"

  export PATH="$BD_BIN:$PATH"
  echo "== Building FFmpeg version $version =="

  curl -q -O -L https://github.com/FFmpeg/FFmpeg/archive/$package
  [ $? -ne 0 ] && \
    onFailure "failed to download FFmpeg code"

  tar xzf $package
  [ $? -ne 0 ] && \
    onFailure "failed to untar '$package'"

  pushd FFmpeg-$version
  PKG_CONFIG_PATH="$BD_PREFIX/lib/pkgconfig" ./configure \
    --prefix="$BD_PREFIX" \
    --extra-cflags="-I$BD_PREFIX/include -O2 -fstack-protector-strong -fpie -pie -Wl,-z,relro,-z,now -D_FORTIFY_SOURCE=2" \
    --extra-ldflags="-L$BD_LIB" \
    --extra-libs=-lpthread \
    --extra-libs=-lm \
    --bindir="$BD_BIN" \
    --enable-libfreetype \
    --enable-openssl \
    --enable-shared \
    --enable-pic \
    --disable-static \
    --disable-gpl \
    --disable-nonfree \
    --disable-version3 \
    --disable-debug \
    --disable-ffplay \
    --disable-libxcb \
    --disable-libxcb-shm \
    --disable-libxcb-xfixes \
    --disable-libxcb-shape \
    --disable-lzma \
    --disable-doc
  make && make install
  [ $? -ne 0 ] && \
    onFailure "error: failed to build FFmpeg version $version"
  popd

  echo "== Completed building FFmpeg version $version =="
  return 0
}

function copyFFMpegAndFFProbe() {
  echo "== Copying FFMpeg and FFProbe binaries to their corresponding Lambda layer directory =="

  local ffmpegDir="/packages/ffmpeg"
  local ffmpegBinDir="$ffmpegDir/bin"
  local ffmpegLibDir="$ffmpegDir/lib"

  local ffprobeDir="/packages/ffprobe"
  local ffprobeBinDir="$ffprobeDir/bin"
  local ffprobeLibDir="$ffprobeDir/lib"

  mkdir -p $ffmpegDir $ffmpegBinDir $ffmpegLibDir $ffprobeDir $ffprobeBinDir $ffprobeLibDir

  # copy ffmpeg, ffprobe binaries and shared libraries
  cp -v $BD_BIN/ffmpeg "$ffmpegBinDir"
  cp -v $BD_BIN/ffprobe "$ffprobeBinDir"
  cp -av $BD_LIB/*.so* "$ffmpegLibDir"
  cp -av $BD_LIB/*.so* "$ffprobeLibDir"

  # copy system libraries
  cp -av /lib64/libbz2.so* "$ffmpegLibDir"
  cp -av /lib64/libbz2.so* "$ffprobeLibDir"
  cp -av /lib64/libfreetype.so* "$ffmpegLibDir"
  cp -av /lib64/libfreetype.so* "$ffprobeLibDir"
  cp -av /lib64/libpng*.so* "$ffmpegLibDir"
  cp -av /lib64/libpng*.so* "$ffprobeLibDir"

  echo "== Copied FFMpeg and FFProbe binaries to their corresponding Lambda layer directory =="
  return 0
}

buildNASM
buildYASM
buildFFMpeg
copyFFMpegAndFFProbe


echo "================================================================================"
echo "Installing ffmpeg-python package"
echo "================================================================================"
pip3.8 install -q ffmpeg-python -t /packages/ffmpeg/python/lib/python3.8/site-packages


echo "================================================================================"
echo "Installing MediaReplayEnginePluginHelper library"
echo "================================================================================"
pip3.8 install -q /packages/Media_Replay_Engine_Plugin_Helper-1.0.0-py3-none-any.whl -t /packages/MediaReplayEnginePluginHelper/python/lib/python3.8/site-packages


echo "================================================================================"
echo "Installing MediaReplayEngineWorkflowHelper library"
echo "================================================================================"
pip3.8 install -q /packages/Media_Replay_Engine_Workflow_Helper-1.0.0-py3-none-any.whl -t /packages/MediaReplayEngineWorkflowHelper/python/lib/python3.8/site-packages


echo "================================================================================"
echo "Installing timecode package"
echo "================================================================================"
pip3.8 install -q timecode -t /packages/timecode/python/lib/python3.8/site-packages


echo "================================================================================"
echo "Creating zip files for Lambda layers"
echo "================================================================================"
cd /packages/MediaReplayEnginePluginHelper/
zip -q -r /packages/MediaReplayEnginePluginHelper.zip .

cd /packages/MediaReplayEngineWorkflowHelper/
zip -q -r /packages/MediaReplayEngineWorkflowHelper.zip .

cd /packages/timecode/
zip -q -r /packages/timecode.zip .

cd /packages/ffmpeg/
zip -q -r /packages/ffmpeg.zip .

cd /packages/ffprobe/
zip -q -r /packages/ffprobe.zip .

# Clean up build environment
cd /packages/
rm -rf /packages/ffmpeg-sources/
rm -rf /packages/MediaReplayEnginePluginHelper/
rm -rf /packages/MediaReplayEngineWorkflowHelper/
rm -rf /packages/timecode/
rm -rf /packages/ffmpeg/
rm -rf /packages/ffprobe/

echo "Zip files have been saved to docker volume /data. You can copy them locally like this:"
echo "docker run --rm -it -v \$(pwd):/packages <docker_image>"
echo "================================================================================"
