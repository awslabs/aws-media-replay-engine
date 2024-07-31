import { Flex, Placeholder, Text, View } from '@aws-amplify/ui-react';
import { faArrowLeft } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { FC, RefObject } from 'react';
import ReactPlayer from 'react-player';
import { Link, useNavigate } from 'react-router-dom';

import { LiveNowTag } from './components';

import { useNewsPageContext, useSessionContext } from '@src/contexts';
import { EventStatuses, Routes } from '@src/enums';
import { WHITE } from '@src/theme';
import { formatDate } from '@src/utils';

interface LeftPanelProps {
  playerRef: RefObject<ReactPlayer>;
}

export const LeftPanel: FC<LeftPanelProps> = ({ playerRef }) => {
  const navigate = useNavigate();

  const { event } = useSessionContext();

  const { setCurrentPlayedVideo, currentPlayedVideo, videoLink } =
    useNewsPageContext();

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
    </View>
  );
};
