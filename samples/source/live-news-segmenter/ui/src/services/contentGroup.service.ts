import { query } from '@src/api';
import { ApiNames, ApiMethods, ApiPaths } from '@src/enums';
import { ContentGroupServices } from '@src/types';

export const contentGroupServices: ContentGroupServices = {
    getContentGroup: () => query(ApiMethods.GET, ApiNames.CONTENT_GROUP, ApiPaths.CONTENT_GROUP_ALL),
}