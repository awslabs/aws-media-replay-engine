import { query } from '@src/api';
import { ApiNames, ApiMethods, ApiPaths } from '@src/enums';
import { UserServices } from '@src/types';
import { setApiPath } from '@src/utils';

export const userFavoriteServices: UserServices = {
    getUserFavorite: (program, event, user_name) => query(
        ApiMethods.GET,
        ApiNames.THEME,
        setApiPath(ApiPaths.USER_FAVORITE, [program, event, user_name, ""]),
    ),
    postUserFavorite: (program, event, user_name, body) => query(
        ApiMethods.POST,
        ApiNames.THEME,
        setApiPath(ApiPaths.USER_FAVORITE, [program, event, user_name, ""]),
        body,
    ),
    deleteUserFavorite: (program, event, user_name, start) => query(
        ApiMethods.DEL,
        ApiNames.THEME,
        setApiPath(ApiPaths.USER_FAVORITE, [program, event, user_name, start]),
    )
}