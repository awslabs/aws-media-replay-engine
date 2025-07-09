import { ApiPaths } from '@src/enums';

type ApiPathValues = (typeof ApiPaths)[keyof typeof ApiPaths];

export const setApiPath = (path: ApiPathValues, params: string[] = []) => {
  let newPath = path as string;
  params.forEach((param) => {
    newPath = newPath.replace(/{\w+}/, param);
  });
  return newPath;
};
