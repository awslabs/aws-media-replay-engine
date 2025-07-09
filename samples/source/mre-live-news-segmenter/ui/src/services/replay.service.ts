import { query } from '@src/api';
import { ApiMethods, ApiNames, ApiPaths } from '@src/enums';
import { ReplayServices } from '@src/types';
import { ReplayRequest } from '@src/types';
import { setApiPath } from '@src/utils';

export const replayServices: ReplayServices = {
  getReplayList: () =>
    query(ApiMethods.GET, ApiNames.REPLAY, setApiPath(ApiPaths.REPLAY_LIST)),
  getReplayListByEvent: (program: string, event: string) =>
    query(
      ApiMethods.GET,
      ApiNames.REPLAY,
      setApiPath(ApiPaths.REPLAY_LIST_BY_EVENT, [program, event]),
    ),
  postReplay: (replayRequest: ReplayRequest) =>
    query(ApiMethods.POST, ApiNames.REPLAY, setApiPath(ApiPaths.REPLAY), {
      body: replayRequest,
    }),
  getReplayById: (program: string, event: string, id: string) =>
    query(
      ApiMethods.GET,
      ApiNames.REPLAY,
      setApiPath(ApiPaths.REPLAY_BY_ID, [program, event, id]),
    ),
};
