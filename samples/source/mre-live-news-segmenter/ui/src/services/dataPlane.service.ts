import { query } from '@src/api';
import { ApiMethods, ApiNames, ApiPaths } from '@src/enums';
import { DataPlaneServices } from '@src/types';
import { setApiPath } from '@src/utils';

export const dataPlaneServices: DataPlaneServices = {
  getSegmentsV2: (name, program, classifier, tracknumber) =>
    query(
      ApiMethods.GET,
      ApiNames.DATAPLANE,
      setApiPath(ApiPaths.SEGMENTS_V2, [
        name,
        program,
        classifier,
        tracknumber,
      ]),
    ),
  getPreviewInfo: (name, program, start, duration, tracknumber, classifier) =>
    query(
      ApiMethods.GET,
      ApiNames.DATAPLANE,
      setApiPath(ApiPaths.PREVIEW_INFO, [
        name,
        program,
        start,
        duration,
        tracknumber,
        classifier,
      ]),
    ),
  postAttributes: (program, event, start, end, body) =>
    query(
      ApiMethods.POST,
      ApiNames.DATAPLANE,
      setApiPath(ApiPaths.ATTRIBUTES, [program, event, start, end]),
      body,
    ),
  postSearchSeries: (body) =>
    query(ApiMethods.POST, ApiNames.DATAPLANE, ApiPaths.SEARCH_SERIES, body),
};
