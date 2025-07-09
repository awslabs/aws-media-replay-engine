import { query } from '@src/api';
import { ApiMethods, ApiNames } from '@src/enums';
import { StreamingServices } from '@src/types';

export const streamingServices: StreamingServices = {
  postStreamingSearch: (body) =>
    query(ApiMethods.POST, ApiNames.STREAMING, '', body, {}, 'reader'),
};
