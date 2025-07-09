import { query } from '@src/api';
import { LIMIT } from '@src/constants';
import { ApiMethods, ApiNames, ApiPaths, SortOrders } from '@src/enums';
import { ThemeServices } from '@src/types';
import { setApiPath } from '@src/utils';

export const themeServices: ThemeServices = {
  refreshEventThemes: (program, event, queryParams) =>
    query(
      ApiMethods.GET,
      ApiNames.THEME,
      setApiPath(ApiPaths.REFRESH_EVENT_THEMES, [program, event]),
      {},
      {
        limit: LIMIT,
        order: SortOrders.ASC,
        ...queryParams,
      },
    ),
  getChildThemes: (queryParams) =>
    query(
      ApiMethods.GET,
      ApiNames.THEME,
      setApiPath(ApiPaths.GET_CHILD_THEMES, [
        queryParams.program,
        queryParams.event,
        queryParams.plugin_name,
        queryParams.start,
        queryParams.end,
      ]),
    ),
};
