import { Flex, Heading, Loader, Text, View } from '@aws-amplify/ui-react';
import { faCirclePlay, faHeart } from '@fortawesome/free-regular-svg-icons';
import {
  faXmark,
  faHeart as solidFaHeart,
} from '@fortawesome/free-solid-svg-icons';
import { useMutation } from '@tanstack/react-query';
import { FC, useMemo } from 'react';
import { LazyLoadImage } from 'react-lazy-load-image-component';
import 'react-lazy-load-image-component/src/effects/blur.css';

import { StlyedCard, StyledIcon } from './style';

import { useNewsPageContext, useSessionContext } from '@src/contexts';
import { ApiMethods, ApiPaths } from '@src/enums';
import { services } from '@src/services';
import { AWS_BORDER_COLOR, AWS_CLOSE_ICON_COLOR, WHITE } from '@src/theme';
import { ChildThemeDto } from '@src/types';
import { formatSecondsToTime } from '@src/utils';

interface BaseSegmentProps {
  segment: ChildThemeDto;
  className: string;
}

export const BaseSegment: FC<BaseSegmentProps> = ({ segment, className }) => {
  const { followTopics, setFollowTopics, setCurrentSegment } =
    useNewsPageContext();
  const { user, event } = useSessionContext();

  const isFollowed = useMemo(() => {
    return followTopics.some(
      (topic) => topic.Start + topic.End === segment.Start + segment.End,
    );
  }, [followTopics, segment]);

  const { mutate: postUserFavorite, isPending } = useMutation({
    mutationKey: [`${ApiPaths.USER_FAVORITE}${ApiMethods.POST}`],
    mutationFn: () =>
      services.postUserFavorite(event.Program, event.Name, user.username, {
        body: {
          start: segment.Start,
        },
      }),
  });

  const { mutate: deleteUserFavorite, isPending: isPendingDelete } =
    useMutation({
      mutationKey: [`${ApiPaths.USER_FAVORITE}${ApiMethods.DEL}`],
      mutationFn: () =>
        services.deleteUserFavorite(
          event.Program,
          event.Name,
          user.username,
          segment.Start,
        ),
    });

  const handleClickPostUserFavorite = () => {
    setFollowTopics([segment]);
    postUserFavorite();
  };

  const handleClickDeleteUserFavorite = () => {
    setFollowTopics([segment]);
    deleteUserFavorite();
  };

  return (
    <StlyedCard variation="outlined" className={className}>
      <View
        textAlign="right"
        fontSize={12}
        className="icon--xmark"
        color={AWS_CLOSE_ICON_COLOR}
      >
        {isPending || isPendingDelete ? (
          <Loader filledColor={WHITE} emptyColor={AWS_BORDER_COLOR} />
        ) : (
          <StyledIcon icon={faXmark} onClick={handleClickDeleteUserFavorite} />
        )}
      </View>
      <Flex>
        <Flex
          direction={'column'}
          fontSize={12}
          justifyContent="space-between"
          alignItems={'center'}
        >
          <Text fontSize={14} fontWeight={700}>
            {formatSecondsToTime(+segment.Start)}
          </Text>
          {segment.OriginalThumbnailLocation ? (
            <LazyLoadImage
              src={segment.OriginalThumbnailLocation}
              alt={segment.Label}
              width={96}
              height={54}
              effect="blur"
            />
          ) : (
            <View width={96} height={54} />
          )}
          <StyledIcon
            icon={faCirclePlay}
            onClick={() => setCurrentSegment(segment)}
          />
        </Flex>
        <View flex={2}>
          <Heading level={6} fontSize={12} fontWeight={700}>
            {segment.Label}
          </Heading>
          <Text className="segment__summary">
            {!segment.Summary.length ? (
              <span style={{ height: 10 }}></span>
            ) : (
              segment.Summary
            )}
          </Text>
          <View className="icon--heart">
            {isPending || isPendingDelete ? (
              <Loader filledColor={WHITE} emptyColor={AWS_BORDER_COLOR} />
            ) : (
              <StyledIcon
                icon={isFollowed ? solidFaHeart : faHeart}
                onClick={
                  isFollowed
                    ? handleClickDeleteUserFavorite
                    : handleClickPostUserFavorite
                }
              />
            )}
          </View>
        </View>
      </Flex>
    </StlyedCard>
  );
};
