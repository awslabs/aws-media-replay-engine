export interface SegmentV2Dto {
  OriginalClipLocation: string;
  OriginalThumbnailLocation: string;
  OptimizedClipLocation: string;
  OptimizedThumbnailLocation: string;
  StartTime: number;
  Label: string;
  FeatureCount: string;
  OrigLength: number;
  OptoLength: number;
  // eslint-disable-next-line
  OptimizedDurationPerTrack: any[];
  OptoStartCode: string;
  OptoEndCode: string;
  Summary?: string;
}
