export interface PreviewInfoDto {
    RangeEvents: RangeEvent[]
    RangeEventsChart: RangeEventsChart[]
    RangeLabels: string[]
    Features: Feature[]
    FeatureLabels: string[]
    OriginalClipLocation: string
}

interface RangeEvent {
    Marker: string
    Start: number
    Duration: number
    Label: string
}

interface RangeEventsChart {
    DetectSpeech?: number[]
    Start: number
    DetectSentiment?: number[]
    SegmentNews?: number[]
}

interface Feature {
    "DetectCelebrities-Chris Wallace, "?: number
    featureAt: number
    "DetectSceneLabels-The iamge has been described"?: number
}
