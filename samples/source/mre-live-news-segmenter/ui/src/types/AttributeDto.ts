import { Attributes } from '@src/enums';

export interface AttributeDto {
  [Attributes.DETECT_SPEECH]?: DetectSpeech[];
  [Attributes.DETECT_SENTIMENT]?: DetectSentiment[];
  SegmentNews?: SegmentNews[];
  DetectCelebrities: DetectCelebrity[];
  DetectSceneLabels: DetectSceneLabel[];
}

export interface DetectSpeech {
  Label: string;
  Transcription: string;
  Speaker: string;
  Start: number;
}

export interface DetectSentiment {
  neutral_score: number;
  Label: string;
  Transcription: string;
  positive_flag: boolean;
  mixed_score: number;
  positive_score: number;
  negative_flag: boolean;
  negative_score: number;
  neutral_flag: boolean;
  mixed_flag: boolean;
  Start: number;
}

export interface SegmentNews {
  Image_Summary: string;
  Label: string;
  Celebrities: string;
  Sentiment: string;
  Summary: string;
  Transcript: string;
  Start: number;
}

export interface DetectCelebrity {
  Label: string;
  Start: number;
}

export interface DetectSceneLabel {
  Image_Summary: string;
  Label: string;
  Start: number;
}
