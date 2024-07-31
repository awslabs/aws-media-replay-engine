import { query } from '@src/api';
import { ApiNames, ApiMethods, ApiPaths } from '@src/enums';
import { ProfileServices as ProfileServiceTypes } from '@src/types';
import { setApiPath } from '@src/utils';

export const profileServices: ProfileServiceTypes = {
    getProfile: (profile: string) => query(ApiMethods.GET, ApiNames.PROFILE, setApiPath(ApiPaths.PROFILE, [profile]))
}