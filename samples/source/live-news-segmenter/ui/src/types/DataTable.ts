import { DetectSpeech, DetectSentiment, SegmentNews } from '@src/types';

export type DataTable = DetectSpeech & {
    Sentiment: DetectSentiment['Label'];
    ImageSummary: SegmentNews['Image_Summary'];
    Celebrities: SegmentNews['Celebrities'];
    Description: SegmentNews['Label'];
};