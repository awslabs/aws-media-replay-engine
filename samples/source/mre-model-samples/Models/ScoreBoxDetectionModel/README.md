# Score Box Detection Model #

**MRE Plugin Class**
- Featurer

**Description**  
This model is an object detection model. It's used to detect score box from the screen. It will output coordinates of the boundingbox.


**Use Cases**:
- Any sports broadcast with score boxes

**Model Type**:
- Custom model trained from Amazon Rekognition Custom Labels

**Methods for training data collection and annotation**
- You can directly import training images and label manifest file by following the notebook
- If you only have training images but no labels, you can annotate the images by following this [document](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/creating-datasets.html)
- This [blog](https://aws.amazon.com/blogs/machine-learning/part-1-end-to-end-solution-building-your-own-brand-detection-and-visibility-using-amazon-sagemaker-ground-truth-and-amazon-rekognition-custom-labels/) provides an end-to-end solution to extract frame images from a video, set up annotation jobs and finally train a model in Amazon Rekogtion Custom Labels.

**Methods for model training**  
- See the notebook  

**Methods for model hosting**
- Models trained from Amazon Rekognition Custom Labels are automatically hosted by Amazon Rekognition. You can use ***StartProjectVersion*** and ***StopProjectVersion*** API to start/stop the model hosting. The ***inference unit*** parameter defines the inference computing power, and you can refer to this [blog](https://aws.amazon.com/blogs/machine-learning/calculate-inference-units-for-an-amazon-rekognition-custom-labels-model/) to calculte the mininum value for inference unit. 

