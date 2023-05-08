FROM public.ecr.aws/lambda/python:3.8 as builder
# install helpers
RUN yum -y install tar xz

# install ffmpeg
RUN curl https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz > /tmp/ffmpeg-release.tar.xz && tar xvf /tmp/ffmpeg-release.tar.xz -C /opt && mv /opt/ffmpeg-* /opt/ffmpeg && cd /opt/ffmpeg && mv model /usr/local/share && mv ffmpeg ffprobe qt-faststart /usr/local/bin && rm /tmp/ffmpeg-release.tar.xz

FROM  public.ecr.aws/lambda/python:3.8 as app
COPY --from=builder /opt/ffmpeg /opt/ffmpeg
COPY --from=builder /usr/local/share/model /usr/local/share
COPY --from=builder /usr/local/bin/ff* /usr/local/bin
COPY --from=builder /usr/local/bin/qt-* /usr/local/bin

RUN yum -y install \
	git \
	unzip

#install aws cli to run the aws commands below
RUN pip install --upgrade awscli

# install lambda function
ARG PLUGIN_NAME
ENV PLUGIN_NAME ${PLUGIN_NAME}

COPY *".py" "${LAMBDA_TASK_ROOT}"
COPY *".json" "${LAMBDA_TASK_ROOT}"
COPY *".md" "${LAMBDA_TASK_ROOT}"
COPY "mre_plugin_helper/python/lib/python3.8/site-packages/." "${LAMBDA_TASK_ROOT}"
COPY requirements.txt .
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

CMD [ "DetectSceneChange.lambda_handler"]