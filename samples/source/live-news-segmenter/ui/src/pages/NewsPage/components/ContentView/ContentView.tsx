import { Flex, Placeholder, View } from '@aws-amplify/ui-react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useReducer, useState } from 'react';
import { FC } from 'react';

import { Contents, QueuedView } from './components';
import { ThemeActionTypes, initialThemeState, themeReducer } from './reducer';
import { LoadMoreButton, StyledView } from './style';

import { useNewsPageContext, useSessionContext } from '@src/contexts';
import { ApiPaths, ContentViews, EventStatuses, SortOrders } from '@src/enums';
import { services } from '@src/services';
import { ChildThemeDto, RefreshEventThemeQueryParams } from '@src/types';

interface ContentViewProps {
  loading: boolean;
  contentView: ContentViews;
  sortOrder: SortOrders;
  setIsLoadingFollowTopics: (value: boolean) => void;
  isLoadingFollowTopics: boolean;
}

const DEFAULT_PLUGIN_NAME = 'SegmentNews';

export const ContentView: FC<ContentViewProps> = ({
  loading,
  contentView,
  sortOrder,
  setIsLoadingFollowTopics,
  isLoadingFollowTopics,
}) => {
  const [notifyModalVisibility, setNotifyModalVisibility] = useState(false);
  const [isNotify, setIsNotify] = useState(false);
  const [isLoading, setIsLoading] = useState(loading);
  const [isFetchingEventThemeData, setIsFetchingEventThemeData] =
    useState(true);

  const [themeState, themeDispatch] = useReducer(
    themeReducer,
    initialThemeState,
  );

  const { event, user } = useSessionContext();
  const { setFollowTopics, setSearchPanelVisibility, searchResults } =
    useNewsPageContext();

  const handleNotifySuccess = () => {
    setIsNotify(true);
    setNotifyModalVisibility(false);
  };

  const { data: profile } = useQuery({
    queryKey: [ApiPaths.PROFILE],
    queryFn: () => services.getProfile(event.Profile),
    refetchOnWindowFocus: false,
  });

  useQuery({
    queryKey: [ApiPaths.REFRESH_EVENT_THEMES],
    queryFn: async () => {
      const queryParams: RefreshEventThemeQueryParams = {
        pluginName:
          profile && profile.success
            ? profile.data.Classifier.Name
            : DEFAULT_PLUGIN_NAME,
        order: sortOrder,
      };
      const response = await services.refreshEventThemes(
        event.Program,
        event.Name,
        queryParams,
      );
      if (response && response.success && response.data.length > 0) {
        themeDispatch({
          type: ThemeActionTypes.SET_MULTIPLE,
          payload: {
            themeList: response.data,
            startFrom: response.StartFrom ?? '',
          },
        });
      }
      setIsFetchingEventThemeData(false);
      return response;
    },
    refetchOnWindowFocus: false,
    enabled: Object.keys(event).length > 0 && profile && profile.success,
  });

  const handleLoadEventTheme = async (
    sortOrder: SortOrders,
    loadMore: boolean,
  ) => {
    setSearchPanelVisibility(false);
    const { themeList, startFrom } = themeState;
    const queryParams: RefreshEventThemeQueryParams = {
      pluginName:
        profile && profile.success
          ? profile.data.Classifier.Name
          : DEFAULT_PLUGIN_NAME,
      order: sortOrder,
    };
    if (loadMore) {
      queryParams['start_from'] = startFrom;
    }
    const response = await services.refreshEventThemes(
      event.Program,
      event.Name,
      queryParams,
    );
    if (response && response.success && response.data.length > 0) {
      themeDispatch({
        type: ThemeActionTypes.SET_MULTIPLE,
        payload: {
          themeList: loadMore
            ? [...themeList, ...response.data]
            : response.data,
          startFrom: response.StartFrom ?? '',
          loadMore: false,
        },
      });
      refetchUserFavoriteData();
    }
    setIsFetchingEventThemeData(false);
  };

  const {
    data: userFavoriteData,
    isFetching: isFetchingUserFavoriteData,
    refetch: refetchUserFavoriteData,
  } = useQuery({
    queryKey: [ApiPaths.USER_FAVORITE],
    queryFn: () =>
      services.getUserFavorite(event.Program, event.Name, user.username),
    refetchOnWindowFocus: false,
    enabled:
      Object.keys(event).length > 0 && event.Status !== EventStatuses.QUEUED,
  });

  useEffect(() => {
    if (!isFetchingUserFavoriteData && !isFetchingEventThemeData) {
      setIsLoadingFollowTopics(false);
      setIsLoading(false);
    }
  }, [
    isFetchingUserFavoriteData,
    isFetchingEventThemeData,
    setIsLoadingFollowTopics,
  ]);

  const segments = useMemo(() => {
    return themeState.themeList;
  }, [themeState.themeList]);

  const handleLoadMore = () => {
    if (!isFetchingEventThemeData && themeState.startFrom.length) {
      themeDispatch({
        type: ThemeActionTypes.SET_LOAD_MORE,
        payload: true,
      });
      handleLoadEventTheme(sortOrder, true);
    }
  };

  useEffect(() => {
    if (isFetchingUserFavoriteData) {
      setFollowTopics([], true);
      setIsLoadingFollowTopics(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    isFetchingUserFavoriteData,
    setIsLoadingFollowTopics,
    isFetchingEventThemeData,
  ]);

  useEffect(() => {
    if (
      userFavoriteData &&
      userFavoriteData.success &&
      !isFetchingUserFavoriteData &&
      themeState.themeList.length > 0
    ) {
      const favorites = userFavoriteData.data;
      const followTopics = themeState.themeList.reduce(
        (arr: ChildThemeDto[], theme) => {
          if (favorites.some((favorite) => favorite.start === theme.Start)) {
            arr.push(theme);
          }
          return arr;
        },
        [],
      );
      setFollowTopics(followTopics, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeState.themeList, userFavoriteData, isFetchingUserFavoriteData]);

  const handleRefresh = (_sortOrder?: SortOrders) => {
    if (!isFetchingEventThemeData) {
      setIsLoadingFollowTopics(true);
      setIsFetchingEventThemeData(true);
      themeDispatch({
        type: ThemeActionTypes.SET_THEME_LIST,
        payload: [],
      });
      setTimeout(() => {
        handleLoadEventTheme(_sortOrder ?? sortOrder, false);
      }, 300);
    }
  };

  return (
    <StyledView flex={2} position={'relative'}>
      {!isLoading && event.Status === EventStatuses.QUEUED && (
        <QueuedView
          setNotifyModalVisibility={setNotifyModalVisibility}
          isNotified={isNotify}
          notifyModalVisibility={notifyModalVisibility}
          handleNotifySuccess={handleNotifySuccess}
        />
      )}
      {!isLoading && event.Status !== EventStatuses.QUEUED && (
        <>
          <Contents
            contentView={contentView}
            segments={segments}
            onRefresh={handleRefresh}
            isLoading={isFetchingEventThemeData}
            isLoadingFollowTopics={isLoadingFollowTopics}
          />
          {themeState.startFrom.length > 0 && !searchResults.length && (
            <LoadMoreButton
              variation="primary"
              onClick={handleLoadMore}
              isLoading={themeState.loadMore}
            >
              Load More
            </LoadMoreButton>
          )}
        </>
      )}
      <View>
        {isLoading && (
          <Flex padding={'18px 15.5px'} justifyContent="space-between">
            {[1, 2].map((item) => (
              <Placeholder size="large" width={'40%'} height={28} key={item} />
            ))}
          </Flex>
        )}
        {isLoading || isFetchingEventThemeData ? (
          <Placeholder size="large" height={97} />
        ) : null}
      </View>
    </StyledView>
  );
};
