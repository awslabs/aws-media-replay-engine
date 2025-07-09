/* eslint-disable @typescript-eslint/no-explicit-any */
import { ReplayStatuses } from '@src/enums';

export interface ReplayDto {
  Program: string;
  Event: string;
  Requester: string;
  Duration: number | string;
  AudioTrack: number;
  CatchUp: boolean;
  Status: ReplayStatuses;
  DTC: false;
  ReplayId: string;
  Description: string;
  EdlLocation: string;
  HlsLocation: string;
  Resolutions: string[];
  UxLabel: string;
  TransitionName: string;
  TransitionOverride: TransitionOverride;
  HlsVideoUrl?: string;
  Mp4Location?: Mp4Location | string;
}

export interface Mp4Location {
  [key: string]: {
    ReplayClips: string[];
    PreviewVideoUrl: string;
  };
}

interface TransitionOverride {
  FadeOutMs: number;
  FadeInMs: number;
}
