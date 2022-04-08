[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Developers Guide - Incorporating Machine Learning Models

MRE makes use of machine learning model endpoints that you design and implement separately. No specific service is required, but successful POC have been completed using AWS services such as:

- Amazon Rekognition Custom Labels
- Amazon SageMaker

Any ML endpoint that is accessible by the plugin Lambda function will work.

Models are registered with MRE to keep associations with Plugins clear for others who may be configuring profiles.

## Registering a plugin with MRE

Models you want to use with MRE should be registered using the **model** API described here:

[POST /model](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/controlplane-model.html#register-model)

While model endpoints could be specified within the plugin lambda code explicitly, this model registry helps with A/B comparisons as needs change.
