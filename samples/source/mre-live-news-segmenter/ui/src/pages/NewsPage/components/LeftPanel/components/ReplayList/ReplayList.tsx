import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Text,
  View,
} from '@aws-amplify/ui-react';
import { faCirclePlay } from '@fortawesome/free-regular-svg-icons';
import { useState } from 'react';

import { ReplayView } from '../ReplayView';

import { ReplayDto } from '@src/types';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';

interface ReplayListProps {
  replays: ReplayDto[];
}

export const ReplayList = (props: ReplayListProps) => {
  const [openReplayViewModal, setOpenReplayViewModal] = useState(false);
  const [selectedReplay, setSelectedReplay] = useState<ReplayDto | undefined>(
    undefined,
  );
  return (
    <>
      <View height={'50vh'} overflow={'auto'}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell as="th" paddingTop={9} paddingBottom={9}>
                Label
              </TableCell>
              <TableCell as="th" paddingTop={9} paddingBottom={9}>
                <View
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                    textAlign: 'center',
                  }}
                >
                  Status
                </View>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {props.replays.map((replay) => (
              <TableRow key={replay.ReplayId}>
                <TableCell paddingTop={8} paddingBottom={8}>
                  <Text>{replay.UxLabel}</Text>
                </TableCell>
                <TableCell paddingTop={8} paddingBottom={8}>
                  <View
                    style={{
                      display: 'flex',
                      justifyContent: 'center',
                      textAlign: 'center',
                    }}
                  >
                    {replay.Status === 'Complete' ? (
                      <FontAwesomeIcon
                        icon={faCirclePlay}
                        onClick={() => {
                          setSelectedReplay(replay);
                          setOpenReplayViewModal(true);
                        }}
                        style={{ cursor: 'pointer' }}
                        size="xl"
                      />
                    ) : (
                      <Text>{replay.Status}</Text>
                    )}
                  </View>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </View>
      {openReplayViewModal && selectedReplay && (
        <ReplayView
          replay={selectedReplay}
          visible={openReplayViewModal}
          onClose={() => setOpenReplayViewModal(false)}
        ></ReplayView>
      )}
    </>
  );
};
