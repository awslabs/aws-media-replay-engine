import { query } from '@src/api';
import { ApiNames, ApiMethods, ApiPaths } from '@src/enums';
import { EventServices } from '@src/types';
import { setApiPath } from '@src/utils';

export const eventServices: EventServices = {
    getEventList: (content: string) => query(ApiMethods.GET, ApiNames.EVENT, setApiPath(ApiPaths.EVENT_LIST, [content]), {
        limit: 25,
        hasReplays: "true",
        ProjectionExpression: "Name, Start, Program, ContentGroup, Profile, Status, Description, SourceVideoUrl, Created, EdlLocation, HlsMasterManifest, Id"
    }),
    getHlsManifestByEvent:
        (name: string, program: string) => query(ApiMethods.GET, ApiNames.EVENT, setApiPath(ApiPaths.HLS_MANIFEST_BY_EVENT, [name, program]))
}