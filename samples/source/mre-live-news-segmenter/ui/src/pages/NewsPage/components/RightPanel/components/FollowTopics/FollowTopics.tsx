import { Text, View } from '@aws-amplify/ui-react';
import { useState } from 'react';

import { CreateReplay } from '../CreateReplay';

import { BaseLink, BaseScrollableContent, BaseSegment } from '@src/components';
import { useNewsPageContext, useSessionContext } from '@src/contexts';
import { ChildThemeDto } from '@src/types';
import { formatSecondsToTime } from '@src/utils';

export const FollowTopics = () => {
  const { event, user } = useSessionContext();
  const { followTopics, height } = useNewsPageContext();
  const [createReplayModalVisible, setCreateReplayModalVisible] =
    useState(false);

  return followTopics.length > 0 ? (
    <View>
      <BaseScrollableContent height={height}>
        {followTopics.map((segment, index) => (
          <BaseSegment
            key={segment.Start}
            segment={segment}
            className={`position-${index + 1} icon__close--visible`}
          />
        ))}
        <View
          style={{
            display: 'flex',
            alignItems: 'center',
            flexDirection: 'column',
          }}
          margin={10}
        >
          <BaseLink onClick={() => setCreateReplayModalVisible(true)}>
            Generate Replay
          </BaseLink>
        </View>
      </BaseScrollableContent>
      {createReplayModalVisible && (
        <CreateReplay
          visible={createReplayModalVisible}
          onClose={() => {
            setCreateReplayModalVisible(false);
          }}
          program={event.Program}
          event={event.Name}
          user={user.username}
          description={
            'This replay has been created from the following segments:\n' +
            followTopics.reduce((res, theme: ChildThemeDto) => {
              return (
                res +
                `${theme.Label}: ${formatSecondsToTime(+theme.Start)} - ${formatSecondsToTime(+theme.End)}\n`
              );
            }, '')
          }
          specifiedTimestamps={followTopics
            .reduce((res, theme: ChildThemeDto) => {
              return res + `${theme.Start}, ${theme.End}\n`;
            }, '')
            .trim()}
          replayMode="SpecifiedTimestamps"
        />
      )}
    </View>
  ) : (
    <Text fontSize={12} padding="7px 17.5px">
      No selections have been favorite.
    </Text>
  );
};
