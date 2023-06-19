FROM amazonlinux:2

WORKDIR /
RUN yum update -y
RUN yum groupinstall -y "Development Tools"
RUN yum install -y \
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
    openssl-devel \
    libffi-devel \
    wget \
    tar \
    gzip \
    zip

# Install Python 3.8
WORKDIR /
RUN wget https://www.python.org/ftp/python/3.8.12/Python-3.8.12.tgz
RUN tar -xzf Python-3.8.12.tgz
WORKDIR /Python-3.8.12
RUN ./configure --enable-optimizations
RUN make install

# Install Python packages and build zip files at runtime
WORKDIR /
RUN mkdir -p /packages/MediaReplayEnginePluginHelper/python/lib/python3.8/site-packages
RUN mkdir -p /packages/MediaReplayEngineWorkflowHelper/python/lib/python3.8/site-packages
RUN mkdir -p /packages/timecode/python/lib/python3.8/site-packages
RUN mkdir -p /packages/ffmpeg-sources/bin
RUN mkdir -p /packages/ffmpeg-sources/lib
RUN mkdir -p /packages/ffmpeg/bin
RUN mkdir -p /packages/ffmpeg/lib
RUN mkdir -p /packages/ffmpeg/python/lib/python3.8/site-packages
RUN mkdir -p /packages/ffprobe/bin
RUN mkdir -p /packages/ffprobe/lib
COPY ./docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]
