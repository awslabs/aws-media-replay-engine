import { CloseOutlined, SendOutlined } from '@ant-design/icons';
import { Heading, Loader, View } from '@aws-amplify/ui-react';
import { useMutation, useQuery } from '@tanstack/react-query';
import 'animate.css';
import {
  ChangeEvent,
  FC,
  FormEvent,
  MouseEvent,
  useEffect,
  useState,
} from 'react';
import { useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { CreateReplay } from '../CreateReplay';
import { StyleView } from './style';
import {
  BaseButton,
  BaseInput,
  BaseLink,
  BaseScrollableContent,
} from '@src/components';
import { useNewsPageContext, useSessionContext } from '@src/contexts';
import { ApiPaths, Senders } from '@src/enums';
import { services } from '@src/services';
import { AWS_BORDER_COLOR, WHITE } from '@src/theme';
import { ChildThemeDto, Detail } from '@src/types';
import {
  getDetails,
  getSummary,
  getTitles,
} from '@src/utils';

interface SearchPanelProps {
  isLoading: boolean;
}

interface ChatContent {
  id: string;
  from: Senders;
  message: string;
  segmentLabels?: string[];
  details?: Detail[];
}

export const SearchPanel: FC<SearchPanelProps> = ({ isLoading }) => {
  const {
    searchPanelVisibility,
    setSearchPanelVisibility,
    setSearchResults,
    height,
  } = useNewsPageContext();
  const [isShowing, setIsShowing] = useState(false);
  const [chatContent, setChatContent] = useState<ChatContent[]>([]);
  const [formData, setFormData] = useState({ search: '' });
  const [isPending, setIsPending] = useState(false);
  const [currentBotMessageId, setCurrentBotMessageId] = useState('');
  const [isGettingDetails, setIsGettingDetails] = useState(false);
  const [stopLoop, setStopLoop] = useState(false);
  const [reader, setReader] = useState<ReadableStreamDefaultReader<
    AllowSharedBufferSource | undefined
  > | null>(null);
  const [createReplayModalVisible, setCreateReplayModalVisible] =
    useState(false);
  const [createReplayContext, setCreateReplayContext] =
    useState<ChatContent | null>(null);

  const scrollableRef = useRef<HTMLDivElement>(null);

  const { user, event } = useSessionContext();
  const { sessionId } = useNewsPageContext();

  useEffect(() => {
    if (isLoading) {
      setIsShowing(false);
    }
  }, [isLoading]);

  useEffect(() => {
    if (searchPanelVisibility) {
      setIsShowing(true);
    }
  }, [searchPanelVisibility]);

  const { mutateAsync } = useMutation({
    mutationKey: [ApiPaths.SEARCH_SERIES],
    mutationFn: (query: string) =>
      services.postStreamingSearch({
        body: {
          SessionId: sessionId,
          Program: event.Program,
          Event: event.Name,
          Query: query,
        },
      }),
  });

  const { data: profileRawData } = useQuery({
    queryKey: [ApiPaths.PROFILE],
    queryFn: () => services.getProfile(event.Profile),
  });

  const handleScrollTop = () => {
    const element = scrollableRef.current;
    if (element) {
      setTimeout(() => {
        element.scroll({ top: element.scrollHeight, behavior: 'smooth' });
      }, 100);
    }
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (formData.search.length) {
      setChatContent([
        ...chatContent,
        {
          id: uuidv4(),
          from: Senders.ME,
          message: formData.search,
        },
      ]);
      setIsPending(true);
      handleScrollTop();
    }
  };

  const handleViewClipSegment = (
    e: MouseEvent<HTMLAnchorElement>,
    details: Detail[],
  ) => {
    e.preventDefault();
    if (details.length) {
      const eventThemeList = details.map(
        (detail) =>
          ({
            Event: event.Name,
            Program: event.Program,
            ProfileName: event.Profile,
            Start: detail.Start.toString(),
            End: detail.End.toString(),
            Label: detail.Title,
            PluginName:
              profileRawData && profileRawData.success
                ? profileRawData.data.Classifier.Name
                : 'SegmentNews',
            Summary: detail.Content,
          }) as ChildThemeDto,
      );
      setSearchResults(eventThemeList);
    }
  };

  useEffect(() => {
    if (isPending) {
      const query = formData.search;
      setFormData({ search: '' });

      mutateAsync(query).then(async (response) => {
        if (response.success) {
          const id = uuidv4();
          setCurrentBotMessageId(id);
          setIsPending(false);
          setIsGettingDetails(true);

          const reader = response.data;
          setReader(reader);
        }
      });
    }
    // eslint-disable-next-line
  }, [isPending]);

  useEffect(() => {
    if (reader) {
      const handleStream = async () => {
        const botMessage: ChatContent = {
          id: currentBotMessageId,
          from: Senders.BOT,
          message: '',
          details: [],
          segmentLabels: [],
        };

        const decoder = new TextDecoder();

        let allChunks = '';
        const flag = true;
        while (flag) {
          const { done, value } = await reader.read();
          if (done) {
            setIsGettingDetails(false);
            setCurrentBotMessageId('');
            setReader(null);
            break;
          }
          const text = decoder.decode(value);
          allChunks = `${allChunks}${text}`;

          botMessage.message = getSummary(allChunks);
          botMessage.segmentLabels = getTitles(allChunks);
          botMessage.details = getDetails(allChunks);
          setChatContent([...chatContent, botMessage]);

        }

        handleScrollTop();
      };

      handleStream();
    }
    // eslint-disable-next-line
  }, [reader, currentBotMessageId]);

  useEffect(() => {
    // Stop consuming the stream when clicking Cancel Search
    if (stopLoop && reader) {
      reader.cancel();
      setStopLoop(false);
      setIsGettingDetails(false);
      setCurrentBotMessageId('');
      setReader(null);
    }
  }, [stopLoop, reader]);

  const handleCreateReplayFromResponse = (replayContext: ChatContent) => {
    console.log(replayContext);
    setCreateReplayContext(replayContext);
    setCreateReplayModalVisible(true);
  };

  const closeCreateReplayModal = () => setCreateReplayModalVisible(false);

  return isLoading ? null : (
    <>
      <StyleView
        display={!isShowing ? 'none' : 'block'}
        className={`animate__animated ${searchPanelVisibility ? 'animate__fadeInRight' : 'animate__fadeOutRight'}`}
      >
        <Heading level={6} fontSize={18} fontWeight={700} marginBottom={27}>
          Search
        </Heading>
        <span
          className="btn--close"
          onClick={() => setSearchPanelVisibility(false)}
        >
          <CloseOutlined />
        </span>
        <BaseScrollableContent
          height={height - (currentBotMessageId.length > 0 ? 110 : 85)}
          ref={scrollableRef}
        >
          {chatContent.map((content) => (
            <View key={content.id} className={`from--${content.from}`}>
              <p style={{ margin: 0 }}>{content.message}</p>
              {content.segmentLabels && content.segmentLabels.length > 0 && (
                <>
                  <p>
                    Segment title
                    {content.segmentLabels && content.segmentLabels.length > 1
                      ? `s`
                      : ''}
                    :
                  </p>
                  <ul>
                    {content.segmentLabels.map((label, index) => (
                      <li key={label + index}>{label}</li>
                    ))}
                  </ul>
                </>
              )}
              {content.details && content.details.length > 0 && (
                <>
                  <p style={{ marginBottom: 0 }}>
                    <BaseLink
                      onClick={(e) =>
                        handleViewClipSegment(e, content.details ?? [])
                      }
                    >
                      View Clip Segment
                      {content.details && content.details.length > 1 ? `s` : ''}
                    </BaseLink>
                  </p>
                  {content.details && (
                    <p>
                      <BaseLink
                        onClick={() => handleCreateReplayFromResponse(content)}
                      >
                        Generate Replay
                      </BaseLink>
                    </p>
                  )}
                </>
              )}
              {currentBotMessageId === content.id && (
                <View marginTop={14}>
                  <Loader filledColor={WHITE} emptyColor={AWS_BORDER_COLOR} />
                </View>
              )}
            </View>
          ))}
          {isPending && (
            <View>
              <Loader filledColor={WHITE} emptyColor={AWS_BORDER_COLOR} />
            </View>
          )}
        </BaseScrollableContent>
        {currentBotMessageId.length > 0 && (
          <BaseLink
            onClick={(e) => {
              e.preventDefault();
              setStopLoop(true);
            }}
            style={{
              position: 'absolute',
              bottom: 75,
              fontSize: 14,
            }}
          >
            Cancel Search
          </BaseLink>
        )}
        <form className="input__search" onSubmit={handleSubmit}>
          <BaseInput
            placeholder="Enter prompt to get started..."
            name="search"
            onChange={handleChange}
            value={formData.search}
            disabled={isPending || isGettingDetails}
          />
          <BaseButton
            variation="primary"
            type="submit"
            disabled={isPending || isGettingDetails}
          >
            <SendOutlined />
          </BaseButton>
        </form>
      </StyleView>
      {createReplayModalVisible && (
        <CreateReplay
          visible={createReplayModalVisible}
          onClose={closeCreateReplayModal}
          program={event.Program}
          event={event.Name}
          user={user.username}
          description={createReplayContext?.message ?? ''}
          specifiedTimestamps={createReplayContext?.details
            ?.sort((a, b) => {
              const startDiff = a.Start - b.Start;
              if (startDiff !== 0) {
                return startDiff;
              }

              const endDiff = a.End - b.End;
              return endDiff;
            })
            .reduce((res, detail) => {
              return res + `${detail.Start}, ${detail.End}\n`;
            }, '')
            .trim()}
          replayMode="SpecifiedTimestamps"
        />
      )}
    </>
  );
};
