export interface ProfileDto {
  Variables: Variables;
  Enabled: boolean;
  ProcessingFrameRate: number;
  ChunkSize: number;
  MaxSegmentLengthSeconds: number;
  Classifier: Classifier;
  Created: string;
  LastModified: string;
  Labeler: Labeler;
  StateMachineArn: string;
  Id: string;
  ContentGroups: string[];
  Name: string;
}

interface Variables {
  Last_Theme: string;
  Active_Presenter: string;
}

interface Classifier {
  Configuration: Configuration;
  DependentPlugins: DependentPlugin[];
  Version: string;
  Name: string;
}

interface Configuration {
  search_window_seconds: string;
  summary_word_length: string;
}

interface DependentPlugin {
  DependentFor: string[];
  Configuration: Configuration2;
  Version: string;
  Name: string;
}

interface Configuration2 {
  duration_seconds?: string;
  desired_presenters?: string;
  notification_message?: string;
  sns_topic_arn?: string;
  celebrity_list?: string;
  minimum_confidence?: string;
  text_language_code?: string;
  text_attribute?: string;
  training_bucket_name?: string;
  silence_duration_sec?: string;
  speaker_inference_enabled?: string;
  training_upload_enabled?: string;
  bias?: string;
  output_bucket_name?: string;
  show_speaker_labels?: string;
  max_speaker_labels?: string;
  input_bucket_name?: string;
  TrackNumber?: string;
}

interface Labeler {
  Configuration: Configuration3;
  Version: string;
  Name: string;
}

interface Configuration3 {}
