import { Heading, Text, View } from '@aws-amplify/ui-react';
import { faCirclePlay } from '@fortawesome/free-regular-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { FC } from 'react';
import { useNavigate } from 'react-router-dom';

import { BackgroundImage, Content } from './style';

import { BaseButton } from '@src/components';
import { useSessionContext } from '@src/contexts';
import { Routes } from '@src/enums';
import { EventDto } from '@src/types';
import { formatDate } from '@src/utils';

interface UpcomingEventProps {
  event: EventDto;
}

export const UpcomingEvent: FC<UpcomingEventProps> = ({ event }) => {
  const { setEvent } = useSessionContext();

  const navigate = useNavigate();

  const handleSetEvent = (event: EventDto) => {
    setEvent(event);
    navigate(Routes.NEWS_AGENT);
  };

  return (
    <View padding="73px 40px" position={'relative'}>
      <BackgroundImage />
      <Content direction={'column'}>
        <Heading fontSize={32} fontWeight={700} level={1}>
          {event.Name}
        </Heading>
        {event.Description && event.Description.length > 0 && (
          <Text fontSize={14} fontWeight={400}>
            {event.Description}
          </Text>
        )}
        <Text fontSize={18} fontWeight={700}>
          {formatDate(event.Start, 'MMMM d, yyyy @ h:mma zzz')}
        </Text>
        <BaseButton variation="primary" onClick={() => handleSetEvent(event)}>
          <View margin="0 8px 0 0" fontSize={16}>
            <FontAwesomeIcon icon={faCirclePlay} />
          </View>
          Watch
        </BaseButton>
      </Content>
    </View>
  );
};
