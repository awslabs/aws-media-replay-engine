FROM ubuntu:16.04

LABEL maintainer="Amazon AI"

# Specify accept-bind-to-port LABEL for inference pipelines to use SAGEMAKER_BIND_TO_PORT
# https://docs.aws.amazon.com/sagemaker/latest/dg/inference-pipeline-real-time.html
LABEL com.amazonaws.sagemaker.capabilities.accept-bind-to-port=true
# Specify multi-models LABEL to indicate container is capable of loading and serving multiple models concurrently
# https://docs.aws.amazon.com/sagemaker/latest/dg/build-multi-model-build-container.html
LABEL com.amazonaws.sagemaker.capabilities.multi-models=true

ARG TF_URL=https://aws-tensorflow-binaries.s3-us-west-2.amazonaws.com/tensorflow/r2.3_aws/20210813_093824/cpu/py37/tensorflow_cpu-2.3.4-cp37-cp37m-manylinux2010_x86_64.whl
ARG ESTIMATOR_URL=https://aws-tensorflow-binaries.s3-us-west-2.amazonaws.com/estimator/r2.3_aws/20210813_093824/tensorflow_estimator-2.3.0-py2.py3-none-any.whl
# The smdebug pipeline relies for following format to perform string replace and trigger DLC pipeline for validating
# the nightly builds. Therefore, while updating the smdebug version, please ensure that the format is not disturbed.
ARG SMDEBUG_VERSION=1.0.9

ARG MMS_VERSION=1.1.5
ARG MX_URL=https://aws-mxnet-pypi.s3-us-west-2.amazonaws.com/1.6.0/aws_mxnet_mkl-1.6.0-py2.py3-none-manylinux1_x86_64.whl
ARG PYTHON=python3
ARG PYTHON_PIP=python3-pip
ARG PIP=pip3
ARG PYTHON_VERSION=3.6.8

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:/usr/local/lib" \
    PYTHONIOENCODING=UTF-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TEMP=/home/model-server/tmp

RUN apt-get update \
 && apt-get -y install --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    libopencv-dev \
    openjdk-8-jdk-headless \
    vim \
    wget \
    zlib1g-dev \
    ffmpeg \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz \
 && tar -xvf Python-$PYTHON_VERSION.tgz \
 && cd Python-$PYTHON_VERSION \
 && ./configure \
 && make \
 && make install \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
    libreadline-gplv2-dev \
    libncursesw5-dev \
    libssl-dev \
    libsqlite3-dev \
    tk-dev \
    libgdbm-dev \
    libc6-dev \
    libbz2-dev \
 && make \
 && make install \
 && rm -rf ../Python-$PYTHON_VERSION* \
 && ln -s /usr/local/bin/pip3 /usr/bin/pip

RUN ln -s $(which ${PYTHON}) /usr/local/bin/python

RUN ${PIP} --no-cache-dir install --upgrade \
    pip \
    setuptools

WORKDIR /

RUN ${PIP} install --no-cache-dir \
    ${MX_URL} \
    git+git://github.com/dmlc/gluon-nlp.git@v0.9.0 \
    gluoncv==0.6.0 \
    multi-model-server==$MMS_VERSION \
    keras-mxnet==2.2.4.1 \
    #numpy==1.17.4 \
    onnx==1.4.1 \
    numpy==1.18.5 \
    scipy==1.4.1 \
    scikit-learn==0.23 \
    tensorflow==2.3 \
    openl3==0.4.1 \
    audio2numpy \
    ffmpeg-python \
    "sagemaker-mxnet-inference<2"

# This is here to make our installed version of OpenCV work.
# https://stackoverflow.com/questions/29274638/opencv-libdc1394-error-failed-to-initialize-libdc1394
# TODO: Should we be installing OpenCV in our image like this? Is there another way we can fix this?
RUN ln -s /dev/null /dev/raw1394

RUN useradd -m model-server \
 && mkdir -p /home/model-server/tmp \
 && chown -R model-server /home/model-server

COPY mms-entrypoint.py /usr/local/bin/dockerd-entrypoint.py
COPY config.properties /home/model-server

RUN chmod +x /usr/local/bin/dockerd-entrypoint.py

RUN curl https://aws-dlc-licenses.s3.amazonaws.com/aws-mxnet-1.6.0/license.txt -o /license.txt

EXPOSE 8080 8081

#RUN mkdir test_video
#COPY ./1_1718.mp4 test_video/
#COPY ./test.py test_video/
#COPY model/code/entrypoint.py /usr/local/bin/entrypoint.py

ENTRYPOINT ["python", "/usr/local/bin/dockerd-entrypoint.py"]
CMD ["multi-model-server", "--start", "--mms-config", "/home/model-server/config.properties"]
