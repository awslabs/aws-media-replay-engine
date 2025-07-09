import { ChildThemeDto } from '@src/types';

export interface ThemeState {
  themeList: ChildThemeDto[];
  startFrom: string;
  loadMore: boolean;
}

export enum ThemeActionTypes {
  SET_THEME_LIST = 'set_theme_list',
  SET_START_FROM = 'set_start_from',
  SET_LOAD_MORE = 'set_load_more',
  SET_MULTIPLE = 'set_multiple',
}

type ThemeAction =
  | {
      type: ThemeActionTypes.SET_THEME_LIST;
      payload: ChildThemeDto[];
    }
  | {
      type: ThemeActionTypes.SET_START_FROM;
      payload: string;
    }
  | {
      type: ThemeActionTypes.SET_LOAD_MORE;
      payload: boolean;
    }
  | {
      type: ThemeActionTypes.SET_MULTIPLE;
      payload: Partial<ThemeState>;
    };

export const initialThemeState: ThemeState = {
  themeList: [],
  startFrom: '',
  loadMore: false,
};

export const themeReducer = (state: ThemeState, action: ThemeAction) => {
  switch (action.type) {
    case ThemeActionTypes.SET_THEME_LIST:
      return {
        ...state,
        themeList: [...state.themeList, ...action.payload],
      };
    case ThemeActionTypes.SET_START_FROM:
      return {
        ...state,
        startFrom: action.payload,
      };
    case ThemeActionTypes.SET_LOAD_MORE:
      return {
        ...state,
        loadMore: action.payload,
      };
    case ThemeActionTypes.SET_MULTIPLE: {
      const { themeList, startFrom, loadMore } = action.payload;
      return {
        ...state,
        themeList: themeList ? themeList : state.themeList,
        startFrom: typeof startFrom === 'string' ? startFrom : state.startFrom,
        loadMore: typeof loadMore === 'boolean' ? loadMore : state.loadMore,
      };
    }
    default:
      return state;
  }
};
