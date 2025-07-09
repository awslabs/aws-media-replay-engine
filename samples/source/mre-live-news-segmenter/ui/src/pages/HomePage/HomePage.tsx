import { View } from '@aws-amplify/ui-react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import { EventList, UpcomingEvent } from './components';

import { useSessionContext } from '@src/contexts';
import { ApiPaths, EventStatuses, PageIds, SortOrders } from '@src/enums';
import { PageLayout } from '@src/layout';
import { services } from '@src/services';
import { EventDto } from '@src/types';
import { setGeneralLoading, sortEvents } from '@src/utils';

export const HomePage = () => {
  useEffect(() => {
    setGeneralLoading(true);
  }, []);

  // At this stage, only the News content group is available.
  const [currentContentGroup] = useState<string>('News');
  const [eventSortingOrder, setEventSortingOrder] = useState<SortOrders>(
    SortOrders.DESC,
  );
  const [upcomingEvent, setUpcomingEvent] = useState<EventDto | null>(null);

  const { setEvent } = useSessionContext();

  const { data: rawEventListData, isFetching } = useQuery({
    queryKey: [ApiPaths.EVENT_LIST],
    queryFn: () => services.getEventList(currentContentGroup),
    refetchOnWindowFocus: false,
  });

  const eventList: EventDto[] = useMemo(() => {
    if (
      rawEventListData &&
      rawEventListData.success &&
      rawEventListData.data.length > 0
    ) {
      return sortEvents(rawEventListData.data, eventSortingOrder, (e) =>
        new Date(e).getTime(),
      );
    }
    return [];
  }, [eventSortingOrder, rawEventListData]);

  useEffect(() => {
    if (eventList.length > 0 && !upcomingEvent) {
      setUpcomingEvent(
        eventList.find(
          (event) =>
            new Date(event.Start) > new Date() &&
            event.Status === EventStatuses.QUEUED,
        ) ?? null,
      );
    }
  }, [eventList, upcomingEvent]);

  useEffect(() => {
    setEvent({} as EventDto);
  }, [setEvent]);

  return (
    <PageLayout pageId={PageIds.HOME_PAGE}>
      {!isFetching && eventList && !('error' in eventList) && (
        <View>
          {upcomingEvent && <UpcomingEvent event={upcomingEvent} />}
          <EventList
            events={eventList}
            sortOrder={eventSortingOrder}
            setSortOrder={() =>
              setEventSortingOrder(
                eventSortingOrder === SortOrders.ASC
                  ? SortOrders.DESC
                  : SortOrders.ASC,
              )
            }
          />
        </View>
      )}
    </PageLayout>
  );
};
