# Pose Keypoints Extraction Model #

**MRE Plugin Class**
- Featurer

**Description**:  
This model endpoint contains two public models. [YOLOv3](https://arxiv.org/abs/1804.02767) model is used for human detection, and [SimplePose](https://arxiv.org/abs/1911.10529) model for keypoints extraction.  
The model is created based on SageMaker MXNetModel image.


**Use Cases**:  
- Pointing pose detection in the Soccer demo   
- Volley detection in the Tennis demo  
- Any human object/pose related detection  

**Model Type**:  
- Public Models hosted as Amazon SageMaker endpoint  

**Methods for training data collection and annotation**  
N/A

**Methods for model training**  
N/A  

**Methods for model hosting**  
-Download YOLOv3 and SimplePose models from GluonCV model zoo  
-Create SageMaker model based on these two public models  
-Create SageMaker endpoint based on the SageMaker model  
-See details in the notebook   

