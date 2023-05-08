# MRE Model Samples #

Model samples are provided to speed development and provide insights into different approaches for solving various video and audio processing needs. There will be couple of different types of model samples in this repo

- Public models hosted on AWS  
This type of models are generally taken from public model zoos. They are pre-trained and can be directly used by MRE plugins. The samples here will show you how to get these models and steps to host them on AWS.

- Custom models trained from AWS AI services  
To train custom models from AWS AI services such as Amazon Rekognition Custom Labels, Amazon Comprehend Custom classification, etc.
The models trained from this approach can NOT be exported or shared with other AWS accounts.
Jupyter notebooks and README files will be provided to show steps of training with the training data clients/users provided

- Custom models trained from Amazon SageMaker  
This type of models including training a model from scratch or transfer training from a pre-trained model in Amazon SageMaker.
The models trained from this approach can be exported and shared. Jupyter notebooks and README files will be provided to show the training and model hosting.

Each model is organized in this repository in a folder based on it's unique name.  

Each Model folder contains:
- README.md  
- config.json  
- model-training-notebook.ipynb  
- optional-other-files  

***The model README should include the following details:***

- The intended MRE Plugin Class
- Description of what the model is designed to do
- Use cases that describe how it was applied in earlier use
- Model types
- Methods for training data collection and annotation
- Methods for model training
- Methods for model hosting
