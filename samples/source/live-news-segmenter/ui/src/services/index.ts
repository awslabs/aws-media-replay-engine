import { contentGroupServices } from "./contentGroup.service";
import { eventServices } from "./event.service";
import { dataPlaneServices } from "./dataPlane.service";
import { profileServices } from "./profile.service";
import { themeServices } from "./theme.service";
import { userFavoriteServices } from "./userFavorite.service";
import { streamingServices } from "./streaming.service";

export const services = {
    ...contentGroupServices,
    ...eventServices,
    ...dataPlaneServices,
    ...profileServices,
    ...themeServices,
    ...userFavoriteServices,
    ...streamingServices,
}