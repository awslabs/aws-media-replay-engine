import { Flex } from '@aws-amplify/ui-react';
import { useQuery } from '@tanstack/react-query';
import { FC, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactPlayer from 'react-player';
import { Navigate } from 'react-router-dom';

import { ContentView, LeftPanel, RightPanel } from './components';

import { NewsPageContext, useSessionContext } from '@src/contexts';
import {
  ApiPaths,
  ContentViews,
  EventStatuses,
  PageIds,
  Routes,
  SortOrders,
} from '@src/enums';
import { PageLayout } from '@src/layout';
import { ModalClipDetail } from '@src/modals';
import { services } from '@src/services';
import { ChildThemeDto } from '@src/types';
import { sortEvents } from '@src/utils';

interface NewsPageProps {}

export const NewsPage: FC<NewsPageProps> = () => {
  /**
   * @todo: too many states, consider refactoring using useReducer
   */
  const [contentView, setContentView] = useState(ContentViews.TIME);
  const [sortOrder, setSortOrder] = useState(SortOrders.ASC);
  const [followTopics, setFollowTopics] = useState<ChildThemeDto[]>([]);
  const [isLoadingFollowTopics, setIsLoadingFollowTopics] = useState(true);
  const [currentSegment, setCurrentSegment] = useState({} as ChildThemeDto);
  const [modalClipDetailsVisibility, setModalClipDetailsVisibility] =
    useState(false);
  const [searchPanelVisibility, setSearchPanelVisibility] = useState(false);
  const [searchResults, setSearchResults] = useState<ChildThemeDto[]>([]);
  const [currentPlayedVideo, setCurrentPlayedVideo] =
    useState<HTMLVideoElement | null>(null);
  const [height, setHeight] = useState(100 * window.innerHeight * 0.01 - 118);

  const leftPanelVideo = useRef<ReactPlayer>(null);

  const { event } = useSessionContext();

  useEffect(() => {
    const handleResize = () => {
      setHeight(100 * window.innerHeight * 0.01 - 118);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleSetFollowTopics = (
    segments: ChildThemeDto[],
    resetting: boolean = false,
  ) => {
    if (resetting) {
      setFollowTopics(segments);
      return;
    }

    const clonedFollowTopics = structuredClone(followTopics);
    if (!clonedFollowTopics.length) {
      setFollowTopics(segments);
    } else {
      const duplicates = clonedFollowTopics.filter((topic) =>
        segments.some((segment) => segment.Start === topic.Start),
      );

      if (!duplicates.length) {
        setFollowTopics(
          sortEvents([...clonedFollowTopics, ...segments], sortOrder, (e) =>
            Number(e),
          ),
        );
      } else {
        const noDuplicates = clonedFollowTopics.filter(
          (topic) => !segments.some((dup) => dup.Start === topic.Start),
        );
        setFollowTopics(sortEvents(noDuplicates, sortOrder, (e) => Number(e)));
      }
    }
  };

  const handleSetCurrentSegment = (segment: ChildThemeDto) => {
    setCurrentSegment(segment);
    setModalClipDetailsVisibility(true);
  };

  const handleCloseModalClipDetails = () => {
    setModalClipDetailsVisibility(false);
    setCurrentSegment({} as ChildThemeDto);
    if (leftPanelVideo.current) {
      leftPanelVideo.current.getInternalPlayer()?.play();
    }
  };

  const handlePlayVideo = useCallback(
    (video: HTMLVideoElement) => {
      if (currentPlayedVideo) {
        currentPlayedVideo.pause();
      }
      setCurrentPlayedVideo(video);
    },
    [currentPlayedVideo],
  );

  const { data: manifestUrl, isFetching } = useQuery({
    queryKey: [ApiPaths.HLS_MANIFEST_BY_EVENT],
    queryFn: () => services.getHlsManifestByEvent(event.Name, event.Program),
    refetchOnWindowFocus: false,
    enabled:
      Object.keys(event).length > 0 && event.Status !== EventStatuses.QUEUED,
  });

  const videoLink = useMemo(() => {
    if (manifestUrl && manifestUrl.success) {
      return manifestUrl.data.ManifestUrl;
    }
    return '';
  }, [manifestUrl]);

  return !Object.keys(event).length ? (
    <Navigate to={Routes.HOME} />
  ) : (
    <NewsPageContext.Provider
      value={{
        setContentView,
        sortOrder,
        setSortOrder,
        followTopics,
        setFollowTopics: handleSetFollowTopics,
        currentSegment,
        setCurrentSegment: handleSetCurrentSegment,
        searchPanelVisibility,
        setSearchPanelVisibility,
        searchResults,
        setSearchResults,
        currentPlayedVideo,
        setCurrentPlayedVideo: handlePlayVideo,
        height,
        videoLink: isFetching ? 'null' : videoLink,
      }}
    >
      <PageLayout pageId={PageIds.NEWS_EVENT_PAGE}>
        <Flex gap="0">
          <LeftPanel playerRef={leftPanelVideo} />
          <ContentView
            loading={true}
            contentView={contentView}
            sortOrder={sortOrder}
            setIsLoadingFollowTopics={setIsLoadingFollowTopics}
            isLoadingFollowTopics={isLoadingFollowTopics}
          />
          <RightPanel isLoadingFollowTopics={isLoadingFollowTopics} />
        </Flex>
        <ModalClipDetail
          visible={modalClipDetailsVisibility}
          onClose={handleCloseModalClipDetails}
          segment={currentSegment}
        />
      </PageLayout>
    </NewsPageContext.Provider>
  );
};
