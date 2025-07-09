export interface ChildThemeDto {
  ModelEndpoint: string;
  OriginalClipLocation: OriginalClipLocation;
  Image_Summary: string;
  OptoEndCode: string;
  Sentiment: string;
  Summary: string;
  OptimizedClipLocation: OptimizedClipLocation;
  OptoStart: OptoStart;
  ProcessingFrameRate: string;
  Transcript: string;
  OptoStartCode: string;
  PluginClass: string;
  ProgramEventPluginName: string;
  ProgramEvent: string;
  OriginalThumbnailLocation: string;
  End: string;
  Desc: string;
  PluginName: string;
  Start: string;
  OptimizedClipStatus: OptimizedClipStatus;
  Event: string;
  Label: string;
  Celebrities: string;
  NonOptoChunkNumber: string;
  OriginalClipStatus: OriginalClipStatus;
  ChunkSize: string;
  Program: string;
  ExecutionId: string;
  ChunkNumber: string;
  Location: Location;
  HourElapsed: string;
  LabelCode: string;
  Filename: string;
  OptoEnd: OptoEnd;
  PK: string;
  ProfileName: string;
}

interface OriginalClipLocation {
  '1': string;
}

interface OptimizedClipLocation {}

interface OptoStart {}

interface OptimizedClipStatus {}

interface OriginalClipStatus {
  '1': string;
}

interface Location {
  S3Bucket: string;
  S3Key: string;
}

interface OptoEnd {}
