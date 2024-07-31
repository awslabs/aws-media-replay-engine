import { Flex, View } from '@aws-amplify/ui-react';
import { Tooltip } from 'antd';
import Hls from 'hls.js';
import {
  FC,
  RefObject,
  SyntheticEvent,
  useEffect,
  useRef,
  useState,
} from 'react';

import { StyledVideo, VideoWrappper } from './style';

import { useNewsPageContext } from '@src/contexts';
import { AWS_ORANGE } from '@src/theme';
import { formatSecondsToTime } from '@src/utils';

interface ModalClipDetailProps {
  shouldStopVideo: boolean;
  setShouldStopVideo: (shouldStopVideo: boolean) => void;
  endMarkerRef: RefObject<HTMLDivElement>;
  visible: boolean;
}

export const Video: FC<ModalClipDetailProps> = ({
  shouldStopVideo,
  setShouldStopVideo,
  endMarkerRef,
  visible,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  const playerRef = useRef<HTMLVideoElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const {
    setCurrentPlayedVideo,
    currentPlayedVideo,
    currentSegment: segment,
    videoLink,
  } = useNewsPageContext();

  const handlePlay = (e: SyntheticEvent<HTMLVideoElement>) => {
    const video = e.target as HTMLVideoElement;
    if (currentPlayedVideo && currentPlayedVideo.src !== video.src) {
      setCurrentPlayedVideo(video);
    }

    if (endMarkerRef.current) {
      endMarkerRef.current.style.visibility = 'hidden';
    }
  };

  const handleSeedked = (e: SyntheticEvent<HTMLVideoElement>) => {
    if (shouldStopVideo) {
      const video = e.target as HTMLVideoElement;
      const { currentTime } = video;
      const endTime = +segment.End;
      if (!isNaN(endTime) && Math.floor(currentTime) > Math.floor(endTime)) {
        setShouldStopVideo(false);
        if (endMarkerRef.current) {
          endMarkerRef.current.style.display = 'none';
        }
      }
    }
  };

  const handleCanPlay = (e: SyntheticEvent<HTMLVideoElement>) => {
    if (endMarkerRef.current) {
      const video = e.target as HTMLVideoElement;
      const leftPosition = (100 * (+segment.End - 0.5)) / video.duration;
      endMarkerRef.current.style.left = `${leftPosition}%`;
      endMarkerRef.current.style.visibility = 'visible';
    }
  };

  useEffect(() => {
    if (playerRef.current) {
      const video = playerRef.current;
      video.pause();
      video.currentTime = +segment.Start;
    }
  }, [segment.Start, playerRef]);

  useEffect(() => {
    if (!visible) {
      // Reset states
      setIsPlaying(false);
      setCurrentTime(0);

      if (playerRef.current) {
        const video = playerRef.current;
        video.pause();
        video.currentTime = +segment.Start;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  useEffect(() => {
    if (Hls.isSupported() && videoLink.length > 0 && playerRef.current) {
      const video = playerRef.current;
      const hls = new Hls({
        startPosition: +segment.Start,
      });
      hls.loadSource(videoLink);
      hls.attachMedia(video);
    }
  }, [videoLink, segment]);

  useEffect(() => {
    // Stop video when reaching segment's end point in normal mode
    const timer = setInterval(() => {
      if (shouldStopVideo && videoLink.length > 0 && playerRef.current) {
        const video = playerRef.current;
        const { currentTime, ended, paused } = video;
        if (ended || paused) return;
        const endTime = +segment.End;
        if (!isNaN(endTime) && currentTime >= endTime - 0.5) {
          video.pause();
          video.currentTime = +segment.Start;
        }
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [segment, shouldStopVideo, videoLink]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (isPlaying) {
        setCurrentTime(currentTime + 1);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [isPlaying, currentTime]);

  return videoLink.length > 0 ? (
    <>
      <p>
        (Start Time: {formatSecondsToTime(+segment.Start)}, End Time:{' '}
        {formatSecondsToTime(+segment.End)}, Duration:{' '}
        {formatSecondsToTime(+segment.End - +segment.Start)})
      </p>
      <Flex justifyContent={'center'} position={'relative'} ref={wrapperRef}>
        <StyledVideo
          ref={playerRef}
          controls={true}
          onPlay={handlePlay}
          onSeeked={handleSeedked}
          onCanPlay={handleCanPlay}
          style={{
            width: '70%',
          }}
        />
        <VideoWrappper>
          <Tooltip
            title={`Segment ends at ${formatSecondsToTime(+segment.End)}`}
            color={AWS_ORANGE}
          >
            <View id="end-marker" ref={endMarkerRef}></View>
          </Tooltip>
        </VideoWrappper>
      </Flex>
    </>
  ) : null;
};
