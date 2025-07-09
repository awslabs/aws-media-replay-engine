import { ApiNames } from '@src/enums';
import { environments } from '@src/utils';

export const API = {
  [ApiNames.CONTENT_GROUP]: {
    endpoint: environments.API_CONTENT_GROUP,
    region: environments.APP_REGION,
  },
  [ApiNames.EVENT]: {
    endpoint: environments.API_EVENT,
    region: environments.APP_REGION,
  },
  [ApiNames.REPLAY]: {
    endpoint: environments.API_REPLAY,
    region: environments.APP_REGION,
  },
  [ApiNames.DATAPLANE]: {
    endpoint: environments.API_DATAPLANE,
    region: environments.APP_REGION,
  },
  [ApiNames.PROFILE]: {
    endpoint: environments.API_PROFILE,
    region: environments.APP_REGION,
  },
  [ApiNames.THEME]: {
    endpoint: environments.API_THEME,
    region: environments.APP_REGION,
  },
  [ApiNames.STREAMING]: {
    endpoint: environments.API_STREAMING,
    region: environments.APP_REGION,
    service: 'lambda',
  },
};
