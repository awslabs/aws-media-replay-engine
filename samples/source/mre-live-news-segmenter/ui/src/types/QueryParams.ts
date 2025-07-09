import { SortOrders } from '@src/enums';

export interface RefreshEventThemeQueryParams {
  pluginName: string;
  limit?: number;
  start_from?: string;
  order?: SortOrders;
}
