/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {TableCell} from "@material-ui/core";
import CheckIcon from '@material-ui/icons/Check';
import {ListRenderer} from "../../components/ListRenderer/ListRenderer";
import Link from "@material-ui/core/Link";
import {REPLAY_SUMMARY_FORM} from "../../common/Constants";
import _ from "lodash";
import {useHistory} from "react-router-dom";


export const ReplayList = () => {
    const history = useHistory();

    const getRow = (row) => {
        return [
            <TableCell align="left">{row.Program}</TableCell>,
            <TableCell align="left">{row.Event}</TableCell>,
            <TableCell align="left">{row.Duration}</TableCell>,
            <TableCell align="left">{row.Requester}</TableCell>,
            <TableCell align="left">{row.AudioTrack}</TableCell>,
            <TableCell align="left">
                {
                    row.CatchUp &&
                    <CheckIcon/>
                }
            </TableCell>,
            <TableCell align="left">{row.Status}</TableCell>,
        ]
    };

    return (
        <ListRenderer
            fetchPath={'replay/all'}
            getRow={getRow}
            eventFilterInitValue={_.get(history, 'location.state.eventFilter')}
            programFilterInitValue={_.get(history, 'location.state.programFilter')}
            createLink={"/addReplay"}
            header={{
                title: "Replay List",
                addTooltip: "Add new Replay",
                contentGroupFilter: true,
                replayFilter: true,
            }}
            tableHeaders={[
                <TableCell align="left">Program</TableCell>,
                <TableCell align="left" style={{minWidth: 150}}>Event</TableCell>,
                <TableCell align="left" style={{maxWidth: 100}}>Duration (minutes)</TableCell>,
                <TableCell align="left">Requester</TableCell>,
                <TableCell align="left">Audio Track</TableCell>,
                <TableCell align="left">Catch-up</TableCell>,
                <TableCell align="left">Status</TableCell>,
                <TableCell align="left">Actions</TableCell>
            ]}
            emptyTableMessage={<>You don't have any Replays created yet. <Link href="https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/guides/MRE-Developer-Guide-Replays.md" target="_blank">Learn more</Link> about Replays in MRE.</>}
            rows={{
                actions: {
                    viewDetails: {
                        path: "/viewReplay",
                        name: "Replay List",
                        link: "/listReplays",
                        tooltip: "View Replay",
                        replayDetails: `replay/program/#Program/event/#Event/replayid/#ReplayId`, //replace #Program with row.Program, #Event with row.Event and #ReplayId with row.ReplayId in Child
                        inputFieldsMap: REPLAY_SUMMARY_FORM,
                    },
                    clipPreview: {
                        path: "/clipPreview",
                        name: "Replay List",
                        link: "/listReplays"
                    },
                    delete: {
                        path: `replay/event/#Event/program/#Program/id/#ReplayId`,
                        tooltip: "Delete Replay"
                    },
                    Edl: {
                        path: `event/#Event/program/#Program`, //replace #Name and #Program with row.Name and row.Program in child,
                        tooltip: "Export to EDL",
                        showAudioTrackDialog: false
                    },
                    Hls: {
                        path: `replay/program/#Program/event/#Event/hls/replaymanifest/replayid/#ReplayId`,
                        showAudioTrackDialog: false,
                        tooltip: "Export to HLS"
                    },
                    downloadMetadata: {
                        tooltip: "Download Replay data",
                        path: `replay/export/data/#ReplayId/event/#Event/program/#Program`,
                        showAudioTrackDialog: false
                    }

                },
            }}
        />
    );
}