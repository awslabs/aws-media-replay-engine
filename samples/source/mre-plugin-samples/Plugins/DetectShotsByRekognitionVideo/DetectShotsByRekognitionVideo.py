# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import botocore
import boto3
import json
import sys
import time
import ffmpeg
from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

s3_client = boto3.client('s3')

class VideoDetect:
    jobId = ''
    rek = boto3.client('rekognition')
    sqs = boto3.client('sqs')
    sns = boto3.client('sns')
    
    roleArn = ''
    bucket = ''
    video = ''
    startJobId = ''

    sqsQueueUrl = ''
    snsTopicArn = ''
    processType = ''

    def __init__(self, role, bucket, video):    
        self.roleArn = role
        self.bucket = bucket
        self.video = video

    def GetSQSMessageSuccess(self):

        jobFound = False
        succeeded = False
    
        dotLine=0
        while jobFound == False:
            sqsResponse = self.sqs.receive_message(QueueUrl=self.sqsQueueUrl, MessageAttributeNames=['ALL'],
                                          MaxNumberOfMessages=10)
            ###print(sqsResponse)
            if sqsResponse:
                
                if 'Messages' not in sqsResponse:
                    if dotLine<100:
                        print('.', end='')
                        dotLine=dotLine+1
                    else:
                        print()
                        dotLine=0    
                        ####kyle 
                        print('TIMEOUT')
                        break
                    sys.stdout.flush()
                    time.sleep(5)
                    continue

                for message in sqsResponse['Messages']:
                    notification = json.loads(message['Body'])
                    rekMessage = json.loads(notification['Message'])
                    print(rekMessage['JobId'])
                    print(rekMessage['Status'])
                    if rekMessage['JobId'] == self.startJobId:
                        print('Matching Job Found:' + rekMessage['JobId'])
                        jobFound = True
                        if (rekMessage['Status']=='SUCCEEDED'):
                            succeeded=True

                        self.sqs.delete_message(QueueUrl=self.sqsQueueUrl,
                                       ReceiptHandle=message['ReceiptHandle'])
                    else:
                        print("Job didn't match:" +
                              str(rekMessage['JobId']) + ' : ' + self.startJobId)
                    # Delete the unknown message. Consider sending to dead letter queue
                    self.sqs.delete_message(QueueUrl=self.sqsQueueUrl,
                                   ReceiptHandle=message['ReceiptHandle'])


        return succeeded

    def CreateTopicandQueue(self):
      
        millis = str(int(round(time.time() * 1000)))

        #Create SNS topic
        
        snsTopicName="AmazonRekognitionExample" + millis

        topicResponse=self.sns.create_topic(Name=snsTopicName)
        self.snsTopicArn = topicResponse['TopicArn']
        print('SNS created',snsTopicName)
        #create SQS queue
        sqsQueueName="AmazonRekognitionQueue" + millis
        self.sqs.create_queue(QueueName=sqsQueueName)
        self.sqsQueueUrl = self.sqs.get_queue_url(QueueName=sqsQueueName)['QueueUrl']
 
        attribs = self.sqs.get_queue_attributes(QueueUrl=self.sqsQueueUrl,
                                                    AttributeNames=['QueueArn'])['Attributes']
                                        
        sqsQueueArn = attribs['QueueArn']
        print('SQS created',sqsQueueName)
        # Subscribe SQS queue to SNS topic
        self.sns.subscribe(
            TopicArn=self.snsTopicArn,
            Protocol='sqs',
            Endpoint=sqsQueueArn)

        #Authorize SNS to write SQS queue 
        policy = """{{
    "Version":"2012-10-17",
    "Statement":[
    {{
      "Sid":"MyPolicy",
      "Effect":"Allow",
      "Principal" : {{"AWS" : "*"}},
      "Action":"SQS:SendMessage",
      "Resource": "{}",
      "Condition":{{
        "ArnEquals":{{
          "aws:SourceArn": "{}"
        }}
      }}
    }}
    ]
    }}""".format(sqsQueueArn, self.snsTopicArn)
 
        response = self.sqs.set_queue_attributes(
            QueueUrl = self.sqsQueueUrl,
            Attributes = {
                'Policy' : policy
            })

    def DeleteTopicandQueue(self):
        self.sqs.delete_queue(QueueUrl=self.sqsQueueUrl)
        self.sns.delete_topic(TopicArn=self.snsTopicArn)

    def StartSegmentDetection(self, use_sns=False):

        min_Technical_Cue_Confidence = 80.0
        min_Shot_Confidence = 60.0
        max_pixel_threshold = 0.1
        min_coverage_percentage = 60
        print("Running Detection on: " + self.video)
        if use_sns:
            response = self.rek.start_segment_detection(
                Video={"S3Object": {"Bucket": self.bucket, "Name": self.video}},
                NotificationChannel={
                    "RoleArn": self.roleArn,
                    "SNSTopicArn": self.snsTopicArn,
                },
                SegmentTypes=["TECHNICAL_CUE", "SHOT"],
                Filters={
                    "TechnicalCueFilter": {
                        "MinSegmentConfidence": min_Technical_Cue_Confidence,
                        # "BlackFrame": {
                        #     "MaxPixelThreshold": max_pixel_threshold,
                        #     "MinCoveragePercentage": min_coverage_percentage,
                        # },
                    },
                    "ShotFilter": {"MinSegmentConfidence": min_Shot_Confidence},
                }
            )
        else:
            response = self.rek.start_segment_detection(
                Video={"S3Object": {"Bucket": self.bucket, "Name": self.video}},
                SegmentTypes=["TECHNICAL_CUE", "SHOT"],
                Filters={
                    "TechnicalCueFilter": {
                        "MinSegmentConfidence": min_Technical_Cue_Confidence,
                        # "BlackFrame": {
                        #     "MaxPixelThreshold": max_pixel_threshold,
                        #     "MinCoveragePercentage": min_coverage_percentage,
                        # },
                    },
                    "ShotFilter": {"MinSegmentConfidence": min_Shot_Confidence},
                }
            )
        self.startJobId = response["JobId"]
        print(f"Start Job Id: {self.startJobId}")

    def GetSegmentDetectionResults(self, chunk_start):
        maxResults = 10
        paginationToken = ""
        finished = False
        firstTime = True
        outlist = [] 
        while finished == False:
            response = self.rek.get_segment_detection(
                JobId=self.startJobId, MaxResults=maxResults, NextToken=paginationToken
            )
            
            if response['JobStatus'] == 'IN_PROGRESS':
                print('waiting 10s')
                time.sleep(10)
                continue
            if response['JobStatus'] == 'FAILED':
                raise Exception("Rekognition Job Error: " + response['StatusMessage']) 
            if firstTime == True:
                print(f"Status\n------\n{response['JobStatus']}")
                print("\nRequested Types\n---------------")
                for selectedSegmentType in response['SelectedSegmentTypes']:
                    print(f"\tType: {selectedSegmentType['Type']}")
                    print(f"\t\tModel Version: {selectedSegmentType['ModelVersion']}")

                print()
                print("\nAudio metadata\n--------------")
                for audioMetadata in response['AudioMetadata']:
                    print(f"\tCodec: {audioMetadata['Codec']}")
                    print(f"\tDuration: {audioMetadata['DurationMillis']}")
                    print(f"\tNumber of Channels: {audioMetadata['NumberOfChannels']}")
                    print(f"\tSample rate: {audioMetadata['SampleRate']}")
                print()
                print("\nVideo metadata\n--------------")
                for videoMetadata in response["VideoMetadata"]:
                    print(videoMetadata)
                    print(f"\tCodec: {videoMetadata['Codec']}")
                    #print(f"\tColor Range: {videoMetadata['ColorRange']}")
                    print(f"\tDuration: {videoMetadata['DurationMillis']}")
                    print(f"\tFormat: {videoMetadata['Format']}")
                    print(f"\tFrame rate: {videoMetadata['FrameRate']}")
                    print("\nSegments\n--------")

                firstTime = False

            for segment in response['Segments']:

                if segment["Type"] == "TECHNICAL_CUE":
                    print("Technical Cue")
                    print(f"\tConfidence: {segment['TechnicalCueSegment']['Confidence']}")
                    print(f"\tType: {segment['TechnicalCueSegment']['Type']}")

                if segment["Type"] == "SHOT":
                    print("Shot")
                    print(f"\tConfidence: {segment['ShotSegment']['Confidence']}")
                    print(f"\tIndex: " + str(segment["ShotSegment"]["Index"]))
                    outputSeg = {}
                    outputSeg['Label'] = 'SHOT'
                    outputSeg['beg'] = segment['StartTimecodeSMPTE']
                    outputSeg['end'] = segment['EndTimecodeSMPTE']
                    outputSeg['duration'] = segment['DurationSMPTE']
                    outlist.append(outputSeg)

                print(f"\tDuration (milliseconds): {segment['DurationMillis']}")
                print(f"\tStart Timestamp (milliseconds): {segment['StartTimestampMillis']}")
                print(f"\tEnd Timestamp (milliseconds): {segment['EndTimestampMillis']}")
                
                print(f"\tStart timecode: {segment['StartTimecodeSMPTE']}")
                print(f"\tEnd timecode: {segment['EndTimecodeSMPTE']}")
                print(f"\tDuration timecode: {segment['DurationSMPTE']}")

                print(f"\tStart frame number {segment['StartFrameNumber']}")
                print(f"\tEnd frame number: {segment['EndFrameNumber']}")
                print(f"\tDuration frames: {segment['DurationFrames']}")

                print()

            if "NextToken" in response:
                paginationToken = response["NextToken"]
            else:
                finished = True
                
        times_sec = []
        begs_sec = []
        results = []
        for out in outlist:
            time_str = out['duration']
            hh,mm,ss,ms = map(int,time_str.replace(';',':').split(':'))
            time_sec = float("{:.2f}".format(ms/60 + ss + 60*(mm + 60*hh)))
            print(time_str,time_sec)
            times_sec.append(time_sec)
            beg_str = out['beg']
            hh,mm,ss,ms = map(int,beg_str.replace(';',':').split(':'))
            beg_sec = float("{:.2f}".format(ms/60 + ss + 60*(mm + 60*hh))) + chunk_start
            print(beg_str,beg_sec)
            begs_sec.append(beg_sec)
            results.append({'Label':'SHOT','Start':beg_sec,'Duration':time_sec})
        return results
    
def lambda_handler(event, context):
    results = []
    mre_dataplane = DataPlane(event)
    print(event)
    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    # Replace following with the ARN of the AmazonRekognitionServiceRole
    roleArn = 'arn:aws:iam::ACCOUNTNUMBER:role/AmazonRekognitionServiceRole'
    bucket = event['Input']['Media']["S3Bucket"]
    video = event['Input']['Media']["S3Key"] #"***.ts"
    chunk_start = event['Input']['Metadata']['HLSSegment']['StartTime']
      
    try:

        # Download the HLS video segment from S3
        media_path = mre_dataplane.download_media()
        mp4_path = '/tmp/mre_chunk.mp4'
        try:
            stream = ffmpeg.input(media_path)
            out, err = (
                ffmpeg.output(stream, mp4_path)
                .run(capture_stdout=True, capture_stderr=True,overwrite_output=True)
            )
        except ffmpeg.Error as err:
            print(err.stderr)
            raise
        try:
            video_mp4 = video[:-2]+'mp4'
            response = s3_client.upload_file(mp4_path, bucket, video_mp4)
        except botocore.exceptions.ClientError as e:
            logging.error(e)
            return False
        print(f'{media_path} converted to {mp4_path} and uploaded to {video_mp4}')

        analyzer=VideoDetect(roleArn, bucket, video_mp4)
        
        analyzer.StartSegmentDetection()
        results = analyzer.GetSegmentDetectionResults(chunk_start)
        print(f'results:{results}')

        # Add the results of the plugin to the payload (required if the plugin status is "complete"; Optional if the plugin has any errors)
        mre_outputhelper.add_results_to_output(results)

        # Persist plugin results for later use
        mre_dataplane.save_plugin_results(results)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_COMPLETE)

        # Returns expected payload built by MRE helper library
        return mre_outputhelper.get_output_object()

    except Exception as e:
        print(e)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_ERROR)

        # Re-raise the exception to MRE processing where it will be handled
        raise

