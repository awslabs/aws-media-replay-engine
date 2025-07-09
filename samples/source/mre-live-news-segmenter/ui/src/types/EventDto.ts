/* eslint-disable @typescript-eslint/no-explicit-any */
import { EventStatuses } from '@src/enums';

export interface EventDto {
  Profile: string;
  SourceSelection: string;
  Archive: boolean;
  TimecodeSource: string;
  LastKnownMediaLiveConfig: LastKnownMediaLiveConfig;
  Status: EventStatuses;
  Created: string;
  EdlLocation: EdlLocation;
  GenerateOrigClips: boolean;
  FrameRate: string;
  DurationMinutes: number;
  StopMediaLiveChannel: boolean;
  vod_schedule_id: string;
  FirstPts: number;
  Start: string;
  Name: string;
  EventDataExportLocation: string;
  Channel: string;
  Variables: Variables;
  StartFilter: string;
  BootstrapTimeInMinutes: number;
  Program: string;
  PaginationPartition: string;
  HlsMasterManifest: HlsMasterManifest;
  AudioTracks: number[];
  GenerateOptoClips: boolean;
  ContentGroup: string;
  Id: string;
  Description?: string;
  SourceHlsMasterManifest?: string;
}

interface LastKnownMediaLiveConfig {
  InputAttachments: InputAttachment[];
  InputSpecification: InputSpecification;
  Destinations: Destination[];
  Maintenance: Maintenance;
  LogLevel: string;
  RoleArn: string;
  Name: string;
  ChannelClass: string;
  State: string;
  EncoderSettings: EncoderSettings;
  PipelinesRunningCount: number;
  Id: string;
  Arn: string;
  PipelineDetails: any[];
  EgressEndpoints: EgressEndpoint[];
  Tags: Tags;
  ResponseMetadata: ResponseMetadata;
}

interface InputAttachment {
  InputAttachmentName: string;
  InputId: string;
  InputSettings: InputSettings;
}

interface InputSettings {
  DeblockFilter: string;
  FilterStrength: number;
  InputFilter: string;
  SourceEndBehavior: string;
  Smpte2038DataPreference: string;
  AudioSelectors: any[];
  CaptionSelectors: any[];
  DenoiseFilter: string;
}

interface InputSpecification {
  Codec: string;
  MaximumBitrate: string;
  Resolution: string;
}

interface Destination {
  Settings: Setting[];
  Id: string;
  MediaPackageSettings: any[];
}

interface Setting {
  Url: string;
}

interface Maintenance {
  MaintenanceDay: string;
  MaintenanceStartTime: string;
}

interface EncoderSettings {
  CaptionDescriptions: any[];
  AudioDescriptions: AudioDescription[];
  VideoDescriptions: VideoDescription[];
  OutputGroups: OutputGroup[];
  TimecodeConfig: TimecodeConfig;
}

interface AudioDescription {
  AudioSelectorName: string;
  AudioTypeControl: string;
  LanguageCodeControl: string;
  Name: string;
}

interface VideoDescription {
  RespondToAfd: string;
  ScalingBehavior: string;
  CodecSettings: CodecSettings;
  Sharpness: number;
  Name: string;
}

interface CodecSettings {
  H264Settings: H264Settings;
}

interface H264Settings {
  NumRefFrames: number;
  TemporalAq: string;
  FramerateControl: string;
  QvbrQualityLevel: number;
  ParControl: string;
  GopClosedCadence: number;
  FlickerAq: string;
  Profile: string;
  SceneChangeDetect: string;
  ForceFieldPictures: string;
  GopSize: number;
  AdaptiveQuantization: string;
  EntropyEncoding: string;
  SpatialAq: string;
  GopSizeUnits: string;
  AfdSignaling: string;
  Bitrate: number;
  RateControlMode: string;
  ScanType: string;
  BufSize: number;
  TimecodeInsertion: string;
  ColorMetadata: string;
  GopBReference: string;
  LookAheadRateControl: string;
  Level: string;
  MaxBitrate: number;
  Syntax: string;
  SubgopLength: string;
  GopNumBFrames: number;
}

interface OutputGroup {
  Outputs: Output[];
  OutputGroupSettings: OutputGroupSettings;
}

interface Output {
  CaptionDescriptionNames: any[];
  OutputSettings: OutputSettings;
  AudioDescriptionNames: string[];
  OutputName: string;
  VideoDescriptionName: string;
}

interface OutputSettings {
  HlsOutputSettings: HlsOutputSettings;
}

interface HlsOutputSettings {
  H265PackagingType: string;
  NameModifier: string;
  HlsSettings: HlsSettings;
}

interface HlsSettings {
  StandardHlsSettings: StandardHlsSettings;
}

interface StandardHlsSettings {
  AudioRenditionSets: string;
  M3u8Settings: M3u8Settings;
}

interface M3u8Settings {
  Scte35Pid: string;
  ProgramNum: number;
  NielsenId3Behavior: string;
  Scte35Behavior: string;
  TimedMetadataPid: string;
  AudioPids: string;
  VideoPid: string;
  AudioFramesPerPes: number;
  PmtPid: string;
  PcrControl: string;
  TimedMetadataBehavior: string;
}

interface OutputGroupSettings {
  HlsGroupSettings: HlsGroupSettings;
}

interface HlsGroupSettings {
  SegmentationMode: string;
  Destination: Destination2;
  CodecSpecification: string;
  IvSource: string;
  TimedMetadataId3Frame: string;
  RedundantManifest: string;
  OutputSelection: string;
  StreamInfResolution: string;
  CaptionLanguageMappings: any[];
  HlsId3SegmentTagging: string;
  IFrameOnlyPlaylists: string;
  CaptionLanguageSetting: string;
  KeepSegments: number;
  DirectoryStructure: string;
  AdMarkers: any[];
  IndexNSegments: number;
  DiscontinuityTags: string;
  InputLossAction: string;
  Mode: string;
  TsFileMode: string;
  ClientCache: string;
  IvInManifest: string;
  ManifestCompression: string;
  ManifestDurationFormat: string;
  TimedMetadataId3Period: number;
  IncompleteSegmentBehavior: string;
  ProgramDateTimePeriod: number;
  SegmentLength: number;
  ProgramDateTime: string;
  SegmentsPerSubdirectory: number;
}

interface Destination2 {
  DestinationRefId: string;
}

interface TimecodeConfig {
  Source: string;
}

interface EgressEndpoint {
  SourceIp: string;
}

interface Tags {}

interface ResponseMetadata {
  HTTPHeaders: Httpheaders;
  RequestId: string;
  HTTPStatusCode: number;
  RetryAttempts: number;
}

interface Httpheaders {
  date: string;
  'x-amz-cf-pop': string;
  'content-length': string;
  'x-amz-apigw-id': string;
  'x-amzn-requestid': string;
  'access-control-allow-headers': string;
  'access-control-allow-methods': string;
  'access-control-expose-headers': string;
  via: string;
  'access-control-allow-origin': string;
  'x-amzn-trace-id': string;
  'access-control-max-age': string;
  'content-type': string;
  connection: string;
  'x-cache': string;
  'x-amz-cf-id': string;
}

interface EdlLocation {
  '1': string;
}

interface Variables {
  Last_Theme: string;
  Active_Presenter: string;
}

interface HlsMasterManifest {}
