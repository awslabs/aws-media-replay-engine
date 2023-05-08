# Audio Embedding Classification Model 

**MRE Plugin Class**
- Featurer

**Description**:  
This model takes the output from AudioEmbeddingModel, and classify the audio embeddings into predefined classes


**Use Cases**:  
- Ace and double fault serve classification in Tennis demo  
- Any audio embedding classification  

**Model Type**:  
- Custom model trained by Amazon SageMaker Autopilot

**Methods for training data collection and annotation**  
- Get output from AudioEmbeddingModel and save as a CSV file
- Add a AUDIO_CLASS column in the CSV file and annotate each pose with a class name
- An end-to-end solution for audio classification is under development

**Methods for model training**  
- Create an Autopilot job. See details in the Notebook  

**Methods for model hosting**  
- Autopilot job will host an endpoint for the best candiate job
