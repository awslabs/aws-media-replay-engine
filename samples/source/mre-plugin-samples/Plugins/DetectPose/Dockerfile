FROM  public.ecr.aws/lambda/python:3.8-x86_64 as app

RUN yum -y install \
    libsndfile \
	git \
	unzip

#install aws cli to run the aws commands below
RUN pip install --upgrade awscli

# install lambda function
COPY *".py" "${LAMBDA_TASK_ROOT}"
COPY *".json" "${LAMBDA_TASK_ROOT}"
COPY *".md" "${LAMBDA_TASK_ROOT}"
COPY "mre_plugin_helper/python/lib/python3.8/site-packages/." "${LAMBDA_TASK_ROOT}"
COPY requirements.txt .
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY requirements.txt .
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

CMD ["DetectPose.lambda_handler"]