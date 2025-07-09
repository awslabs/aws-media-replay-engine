import { format } from 'date-fns';
import { utcToZonedTime } from 'date-fns-tz';

import { SortOrders } from '@src/enums';

export const formatDate = (dateString: string, formatSring: string) => {
  const date = new Date(dateString);
  const estDate = utcToZonedTime(date, 'America/New_York');
  return format(estDate, formatSring);
};

export const formatSecondsToTime = (totalSeconds: number) => {
  // Calculate hours, minutes, and remaining seconds
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);

  // Pad seconds, minutes, and hours with leading zero if necessary
  const secondsStr = seconds < 10 ? '0' + seconds : seconds;
  const minutesStr = minutes < 10 ? '0' + minutes : minutes;
  const hoursStr = hours < 10 ? '0' + hours : hours;

  // Format as hh:mm:ss
  return hoursStr + ':' + minutesStr + ':' + secondsStr;
};

export const sortEvents = <T>(
  events: T[],
  sortOrder: SortOrders,
  converter: (e: string) => number,
): T[] => {
  if (events.length <= 1) {
    return events;
  }

  const pivot: T = events[0];
  const leftArr: T[] = [];
  const rightArr: T[] = [];

  for (let i = 1; i < events.length; i++) {
    // eslint-disable-next-line
    // @ts-ignore
    if (converter(events[i].Start) < converter(pivot.Start)) {
      leftArr.push(events[i]);
    } else {
      rightArr.push(events[i]);
    }
  }

  return sortOrder === SortOrders.ASC
    ? [
        ...sortEvents(leftArr, sortOrder, converter),
        pivot,
        ...sortEvents(rightArr, sortOrder, converter),
      ]
    : [
        ...sortEvents(rightArr, sortOrder, converter),
        pivot,
        ...sortEvents(leftArr, sortOrder, converter),
      ];
};
