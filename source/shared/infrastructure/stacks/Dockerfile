# Use the official AWS Lambda Python 3.12 base image
FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

# Install cryptography library
RUN pip install cryptography

# Copy the Lambda function code into the container
COPY rsa_keys.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (this is the function in your Python code)
CMD ["rsa_keys.on_event"]
