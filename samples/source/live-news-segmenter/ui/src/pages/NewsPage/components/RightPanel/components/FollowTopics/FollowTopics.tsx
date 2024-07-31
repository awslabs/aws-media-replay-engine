import { Text } from '@aws-amplify/ui-react';

import { BaseScrollableContent, BaseSegment } from '@src/components';
import { useNewsPageContext } from '@src/contexts';

export const FollowTopics = () => {
  const { followTopics, height } = useNewsPageContext();

  return followTopics.length > 0 ? (
    <BaseScrollableContent height={height}>
      {followTopics.map((segment, index) => (
        <BaseSegment
          key={segment.Start}
          segment={segment}
          className={`position-${index + 1} icon__close--visible`}
        />
      ))}
    </BaseScrollableContent>
  ) : (
    <Text fontSize={12} padding="7px 17.5px">
      No selections have been favorite.
    </Text>
  );
};
