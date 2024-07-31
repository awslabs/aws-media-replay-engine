import { TableCell, TableRow } from '@aws-amplify/ui-react';
import { faCaretDown, faCaretUp } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { Tooltip } from 'antd';
import { FC } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from 'styled-components';

import { BaseTable } from '@src/components';
import { useSessionContext } from '@src/contexts';
import { EventStatuses, Routes, SortOrders } from '@src/enums';
import { AWS_CLOSE_ICON_COLOR, AWS_ORANGE } from '@src/theme';
import { BaseFunction, EventDto } from '@src/types';
import { formatDate } from '@src/utils';

interface EventListProps {
  events: EventDto[];
  sortOrder: SortOrders;
  setSortOrder: BaseFunction;
}

const StyledTableCell = styled(TableCell)`
  font-size: 14px;
  font-weight: 400;
`;

export const EventList: FC<EventListProps> = ({
  events,
  sortOrder,
  setSortOrder,
}) => {
  const { setEvent } = useSessionContext();

  const navigate = useNavigate();

  const handleSetEvent = (event: EventDto) => {
    setEvent(event);
    navigate(Routes.NEWS_AGENT);
  };

  return (
    <BaseTable
      tableHead={
        <TableRow>
          <TableCell as="th">Event Name</TableCell>
          <TableCell as="th">
            Time
            <Tooltip
              title={`Sort ${sortOrder === SortOrders.ASC ? 'Descending' : 'Ascending'}`}
              color={AWS_ORANGE}
            >
              <FontAwesomeIcon
                icon={sortOrder === SortOrders.ASC ? faCaretDown : faCaretUp}
                style={{ marginLeft: 25, cursor: 'pointer' }}
                onClick={setSortOrder}
              />
            </Tooltip>
          </TableCell>
          <TableCell as="th">Content Group</TableCell>
          <TableCell as="th">Status</TableCell>
        </TableRow>
      }
      tableBody={events.map((event) => (
        <TableRow key={event.Id}>
          <StyledTableCell color={AWS_ORANGE}>
            <a
              onClick={(e) => {
                e.preventDefault();
                handleSetEvent(event);
              }}
              style={{ cursor: 'pointer' }}
            >
              {event.Name}
            </a>
          </StyledTableCell>
          <StyledTableCell>
            {formatDate(event.Start, 'MM/dd/yyyy, hh:mm zzz')}
          </StyledTableCell>
          <StyledTableCell>{event.ContentGroup}</StyledTableCell>
          <StyledTableCell
            color={
              event.Status === EventStatuses.COMPLETE
                ? 'green'
                : event.Status === EventStatuses.QUEUED
                  ? AWS_CLOSE_ICON_COLOR
                  : '#99CBE4'
            }
          >
            {event.Status}
          </StyledTableCell>
        </TableRow>
      ))}
    />
  );
};
