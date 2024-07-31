import {
    HttpResponseSuccess,
    HttpResponseError,
    EventDto,
    ProfileDto,
    SegmentV2Dto,
    ChildThemeDto,
    RefreshEventThemeQueryParams,
    UserFavoriteDto,
    PreviewInfoDto,
    AttributeDto,
    SearchDto,
} from "@src/types";

type QueryParams<T> = T;

type RequestBody<T> = {
    body: T;
}

export interface ContentGroupServices {
    getContentGroup: () => Promise<HttpResponseSuccess<Record<'Name', string>[]> | HttpResponseError>;
}

export interface EventServices {
    getEventList: (content: string) => Promise<HttpResponseSuccess<EventDto[]> | HttpResponseError>;
    getHlsManifestByEvent: (name: string, program: string) => Promise<HttpResponseSuccess<{
        ManifestUrl: string
    }> | HttpResponseError>;
}

export interface DataPlaneServices {
    getSegmentsV2: (name: string, program: string, classifier: string, tracknumber: string) => Promise<HttpResponseSuccess<{ Segments: SegmentV2Dto[] }> | HttpResponseError>;
    getPreviewInfo:
    (name: string, program: string, start: string, duration: string, tracknumber: string, classifier: string)
        => Promise<HttpResponseSuccess<PreviewInfoDto> | HttpResponseError>;
    postAttributes:
    (program: string, event: string, start: string, end: string, body: RequestBody<{ pluginAttributes: string[] }>)
        => Promise<HttpResponseSuccess<AttributeDto> | HttpResponseError>;
    postSearchSeries: (body: RequestBody<{ Query: string, Program: string, Event: string }>) => Promise<HttpResponseSuccess<SearchDto> | HttpResponseError>;
}

export interface ProfileServices {
    getProfile: (profile: string) => Promise<HttpResponseSuccess<ProfileDto> | HttpResponseError>;
}

export interface ThemeServices {
    refreshEventThemes: (
        program: string,
        event: string,
        query: QueryParams<RefreshEventThemeQueryParams>
    ) => Promise<HttpResponseSuccess<ChildThemeDto[]> | HttpResponseError>;
    getChildThemes: (query: QueryParams<{
        program: string,
        event: string,
        plugin_name: string
        start: string,
        end: string
    }>) => Promise<HttpResponseSuccess<ChildThemeDto[]> | HttpResponseError>;
}

export interface UserServices {
    getUserFavorite: (program: string, event: string, user_name: string) => Promise<HttpResponseSuccess<UserFavoriteDto[]> | HttpResponseError>;
    postUserFavorite: (program: string, event: string, user_name: string, body: RequestBody<{ start: string }>) => Promise<HttpResponseSuccess<string> | HttpResponseError>;
    deleteUserFavorite: (program: string, event: string, user_name: string, start: string) => Promise<HttpResponseSuccess<string> | HttpResponseError>;
}

export interface StreamingServices {
    // eslint-disable-next-line
    postStreamingSearch: (body: RequestBody<{ Query: string, Program: string, Event: string }>) => Promise<HttpResponseSuccess<any> | HttpResponseError>;
}