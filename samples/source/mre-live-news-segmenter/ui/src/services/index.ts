import { contentGroupServices } from './contentGroup.service';
import { dataPlaneServices } from './dataPlane.service';
import { eventServices } from './event.service';
import { profileServices } from './profile.service';
import { replayServices } from './replay.service';
import { streamingServices } from './streaming.service';
import { themeServices } from './theme.service';
import { userFavoriteServices } from './userFavorite.service';

export const services = {
  ...contentGroupServices,
  ...eventServices,
  ...dataPlaneServices,
  ...profileServices,
  ...themeServices,
  ...userFavoriteServices,
  ...streamingServices,
  ...replayServices,
};
