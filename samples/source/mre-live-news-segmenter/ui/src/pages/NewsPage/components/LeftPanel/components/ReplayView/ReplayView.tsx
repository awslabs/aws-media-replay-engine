import {
  Button,
  Card,
  Loader,
  Placeholder,
  Tabs,
  Text,
  View,
} from '@aws-amplify/ui-react';
import { faDownload } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { useQuery } from '@tanstack/react-query';
import { Tooltip } from 'antd';
import { useState } from 'react';
import ReactPlayer from 'react-player';

import { BaseModal } from '@src/components';
import { useSessionContext } from '@src/contexts';
import { ApiPaths } from '@src/enums';
import { services } from '@src/services';
import { AWS_BORDER_COLOR, AWS_ORANGE, WHITE } from '@src/theme';
import { Mp4Location, ReplayDto } from '@src/types';

interface ReplayViewProps {
  replay: ReplayDto;
  visible: boolean;
  onClose: () => void;
}

export const ReplayView = (props: ReplayViewProps) => {
  const { replay, visible, onClose } = props;

  const [highlightClipVideoUrl, setHighlightClipVideoUrl] = useState("");
  const [highlightClips, setHighlightClips] = useState<Mp4Location>({});
  const [isLoading, setIsLoading] = useState(false);
  const [replayDownloading, setReplayDownloading] = useState(false);
  const [mp4Resolution, setMp4Resolution] = useState("")
  const [hlsResolution, setHlsResolution] = useState("")
  const { event } = useSessionContext();

  const loadReplayById = async () => {
    setIsLoading(true);
    const replayRaw = await services.getReplayById(
      event.Program,
      event.Name,
      replay.ReplayId,
    );
    setIsLoading(false);
    if (replayRaw && replayRaw.success) {
      if (replayRaw.data) {
        
        if(replayRaw.data.HlsVideoUrl && replayRaw.data.HlsVideoUrl !== '')
        {
          setHlsResolution(replayRaw.data.Resolutions[0].split(" ")[0])
          setHighlightClipVideoUrl(replayRaw.data.HlsVideoUrl);
        }
          

        if(replayRaw.data.Mp4Location &&
          typeof replayRaw.data.Mp4Location !== 'string'){
            setHighlightClips(replayRaw.data.Mp4Location);
            const resolution = Object.keys(replayRaw.data.Mp4Location)[0]
            setMp4Resolution(resolution)
            setHighlightClipVideoUrl(replayRaw.data.Mp4Location[resolution].PreviewVideoUrl)
        } 

        console.log(replayRaw.data.Mp4Location)
        return replayRaw.data;
      }
    }
  };

  const downloadVideo = async (url: string) => {
    try {
      setReplayDownloading(true);
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch video: ${response.statusText}`);
      }

      const blob = await response.blob();
      const urlCreator = window.URL || window.webkitURL;
      const videoUrl = urlCreator.createObjectURL(blob);

      const tag = document.createElement('a');
      tag.href = videoUrl;
      tag.target = '_blank';
      tag.download = 'video.mp4';

      document.body.appendChild(tag);
      tag.click();
      document.body.removeChild(tag);

      // Revoke the object URL to free up memory
      window.URL.revokeObjectURL(videoUrl);
      setReplayDownloading(false);
    } catch (err) {
      console.error('Error downloading video:', err);
      setReplayDownloading(false);
    }
  };

  useQuery({
    queryKey: [ApiPaths.REPLAY_BY_ID],
    queryFn: loadReplayById,
    refetchOnWindowFocus: false,
  });

  return (
    <BaseModal
      visible={visible}
      onClose={onClose}
      header={replay.UxLabel}
      content={
        <View
          display={'flex'}
          style={{ flexDirection: 'column', alignContent: 'center' }}
          maxHeight={800}
        >
          {highlightClipVideoUrl !== '' ? (
            <View marginTop={20}>
              {
                <Tabs
                  justifyContent="flex-start"
                  defaultValue={Object.keys(highlightClips)[0] ?? `HLS - ${hlsResolution}`}
                  onValueChange={(resolution) =>
                    {
                      setMp4Resolution(resolution)
                      setHighlightClipVideoUrl(
                        `${highlightClips[resolution].PreviewVideoUrl}`,
                      )
                    }
                  }
                  items={
                    Object.keys(highlightClips).length > 0
                      ? Object.keys(highlightClips).map((key) => {
                          return {
                            label: key,
                            value: key,
                            content: (
                              <>
                                <ReactPlayer
                                  url={`${highlightClips[key].PreviewVideoUrl}`}
                                  width="100%"
                                  style={{ maxHeight: '60vh' }}
                                  controls={true}
                                  playing={false}
                                  loop={true}
                                />
                              </>
                            ),
                          };
                        })
                      : [
                          {
                            label: `HLS - ${hlsResolution}`,
                            value: `HLS - ${hlsResolution}`,
                            content: (
                              <ReactPlayer
                                url={`${highlightClipVideoUrl}`}
                                width="100%"
                                style={{ maxHeight: '70vh' }}
                                controls={true}
                                playing={false}
                                loop={true}
                              />
                            ),
                          },
                        ]
                  }
                />
              }
            </View>
          ) : isLoading ? (
            <Placeholder size="large" height={97} />
          ) : (
            <Text color="textPrimary">
              No highlight clip has been generated yet. Please try again in a
              while.
            </Text>
          )}
          <Card variation="outlined" marginTop={20}>
            <Text variation="primary" fontWeight={700} fontSize="20px">
              Description
            </Text>
            <Text>{replay.Description}</Text>
          </Card>
          <Tooltip
            title={
              replay.HlsLocation.startsWith('s3://')
                ? 'Download only available for MP4 formatted replay clips'
                : ''
            }
            color={AWS_ORANGE}
          >
            <Button
              disabled={
                replayDownloading || replay.HlsLocation.startsWith('s3://')
              }
              marginTop={10}
              onClick={() => {
                downloadVideo(highlightClips[mp4Resolution].PreviewVideoUrl);
              }}
            >
              {replayDownloading ? (
                <>
                  {' '}
                  Downloading...&nbsp;
                  <Loader filledColor={WHITE} emptyColor={AWS_BORDER_COLOR} />
                </>
              ) : (
                <>
                  Download Replay Video&nbsp;
                  <FontAwesomeIcon icon={faDownload} />
                </>
              )}
            </Button>
          </Tooltip>
        </View>
      }
      width={700}
      footer={null}
    />
  );
};
