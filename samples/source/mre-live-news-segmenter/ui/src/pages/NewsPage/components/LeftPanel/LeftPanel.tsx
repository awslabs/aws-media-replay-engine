import {
  Flex,
  Placeholder,
  Text,
  View,
} from '@aws-amplify/ui-react';
import {
  faArrowLeft,
  faArrowsRotate,
  faFilter,
} from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { useQuery } from '@tanstack/react-query';
import { Tooltip } from 'antd';
import { FC, RefObject, useEffect, useState } from 'react';
import ReactPlayer from 'react-player';
import { Link, useNavigate } from 'react-router-dom';

import { LiveNowTag } from './components';
import { ReplayList } from './components';

import { useNewsPageContext, useSessionContext } from '@src/contexts';
import { ApiPaths, EventStatuses, Routes } from '@src/enums';
import { services } from '@src/services';
import { AWS_ORANGE, WHITE } from '@src/theme';
import { formatDate } from '@src/utils';

interface LeftPanelProps {
  playerRef: RefObject<ReactPlayer>;
}

export const LeftPanel: FC<LeftPanelProps> = ({ playerRef }) => {
  const navigate = useNavigate();

  const [replaysLoading, setReplaysLoading] = useState<boolean>(false);
  const [filterByUser, setFilterByUser] = useState<boolean>(false);

  const { event, user } = useSessionContext();

  const {
    setCurrentPlayedVideo,
    currentPlayedVideo,
    videoLink,
    replays,
    setReplays,
  } = useNewsPageContext();

  useEffect(() => {
    setInterval(() => {
      loadReplays();
    }, 10000);
  }, []);

  const handlePlay = () => {
    if (playerRef.current) {
      const videoTag = playerRef.current.getInternalPlayer();
      if (videoTag) {
        if (!currentPlayedVideo || currentPlayedVideo.src !== videoTag.src) {
          setCurrentPlayedVideo(videoTag as HTMLVideoElement);
        }
      }
    }
  };

  const loadReplays = async () => {
    setReplaysLoading(true);
    const rawReplays = await services.getReplayListByEvent(
      event.Program,
      event.Name,
    );
    if (rawReplays && rawReplays.success) {
      setReplays(rawReplays.data);
      setReplaysLoading(false);
    }
    return rawReplays;
  };

  useQuery({
    queryKey: [ApiPaths.REPLAY_LIST_BY_EVENT],
    queryFn: loadReplays,
    refetchOnWindowFocus: false,
  });

  return (
    <View flex={1} padding="12px 16.5px 0 40px">
      <Flex alignItems={'center'}>
        <Link
          to={Routes.HOME}
          onClick={(e) => {
            e.preventDefault();
            navigate(Routes.HOME);
          }}
        >
          <FontAwesomeIcon icon={faArrowLeft} color={WHITE} />
        </Link>
        <View>
          <Text variation="primary" fontWeight={700} fontSize="20px">
            {event.Name}
          </Text>
          <Text variation="primary" fontWeight={400} fontSize="12px">
            {formatDate(event.Start, 'MMMM d, yyyy @ h:mmaaa z')}
          </Text>
        </View>
      </Flex>
      <View position="relative" marginTop={7}>
        {videoLink.length > 0 && event.Status !== EventStatuses.QUEUED ? (
          <>
            {event.Status === EventStatuses.IN_PROGRESS && <LiveNowTag />}

            {videoLink === 'null' ? (
              <Placeholder size="large" height={97} />
            ) : (
              <ReactPlayer
                url={videoLink}
                playing={true}
                width="100%"
                height="100%"
                controls
                muted
                ref={playerRef}
                onPlay={handlePlay}
              />
            )}
          </>
        ) : (
          <Text variation="primary" fontWeight={400} fontSize="12px">
            No Replay Clips Were Created From This Event. Try Creating Another
            Replay With Different Settings or Using Another Event.
          </Text>
        )}
      </View>
      <View position="relative" marginTop={20}>
        <Flex
          marginBottom={10}
          alignItems={'center'}
          justifyContent={'space-between'}
        >
          <Text variation="primary" fontWeight={700} fontSize="20px">
            Replays
          </Text>
          <View>
            <Tooltip title="Only show replays created by me" color={AWS_ORANGE}>
              <FontAwesomeIcon
                icon={faFilter}
                cursor={'pointer'}
                size="lg"
                color={filterByUser ? AWS_ORANGE : WHITE}
                onClick={async () => {
                  setFilterByUser(!filterByUser);
                }}
              />
            </Tooltip>
            &emsp;
            <Tooltip title="Refresh" color={AWS_ORANGE}>
              <FontAwesomeIcon
                icon={faArrowsRotate}
                cursor={'pointer'}
                size="lg"
                onClick={replaysLoading ? loadReplays : () => {}}
              />
            </Tooltip>
          </View>
        </Flex>

        {!replaysLoading && replays.length !== 0 ? (
          <ReplayList
            replays={
              filterByUser
                ? replays.filter((replay) => {
                    return filterByUser
                      ? replay.Requester === user.username
                      : true;
                  })
                : replays
            }
          />
        ) : replaysLoading ? (
          <ReplayList
            replays={
              filterByUser
                ? replays.filter((replay) => {
                    return filterByUser
                      ? replay.Requester === user.username
                      : true;
                  })
                : replays
            }
          />
        ) : (
          <Text variation="primary" fontWeight={400} fontSize="18px">
            No Replay Clips Were Created From This Event. Try Creating Another
            Replay With Different Settings or Using Another Event.
          </Text>
        )}
      </View>
    </View>
  );
};
