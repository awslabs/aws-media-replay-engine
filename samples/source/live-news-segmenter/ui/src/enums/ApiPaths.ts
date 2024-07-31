export enum ApiPaths {
    // Currently not used
    CONTENT_GROUP_ALL = '/contentgroup/all',
    EVENT_LIST = '/event/contentgroup/{contentgroup}/all',
    HLS_MANIFEST_BY_EVENT = '/event/{name}/hls/stream/program/{program}',
    // Currently not used
    SEGMENTS_V2 = '/event/{name}/program/{program}/profileClassifier/{classifier}/track/{tracknumber}/segments/v2',
    PROFILE = '/profile/{name}',
    REFRESH_EVENT_THEMES = '/refresh-event-themes/{program}/{event}',
    GET_CHILD_THEMES = '/get-child-themes/{program}/{event}/{plugin}/{start}/{end}',
    USER_FAVORITE = '/user-favorites/{program}/{event}/{user_name}/{start}',
    // Currently not used
    PREVIEW_INFO = '/event/{name}/program/{program}/clipstart/{start}/clipduration/{duration}/track/{tracknumber}/classifier/{classifier}/org/previewinfo',
    ATTRIBUTES = '/program/{program}/event/{event}/start/{start}/end/{end}/plugins/output/attributes',
    SEARCH_SERIES = '/search/series',
}