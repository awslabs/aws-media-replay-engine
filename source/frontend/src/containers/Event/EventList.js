/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {TableCell} from "@material-ui/core";
import _ from "lodash";
import moment from "moment";
import Link from "@material-ui/core/Link";
import {ListRenderer} from "../../components/ListRenderer/ListRenderer";
import Button from "@material-ui/core/Button";
import {useNavigate} from "react-router-dom";


export const EventList = () => {
    const navigate = useNavigate();
    const [contentGroup, setContentGroup] = React.useState("ALL")
    const [program, setProgram] = React.useState("ALL")
    const [timeFilterStart, setTimeFilterStart] = React.useState(undefined);
    const [timeFilterEnd, setTimeFilterEnd] = React.useState(undefined);
    const [queryParams, setQueryParams] = React.useState(undefined)

    React.useEffect(() => {
        let today = moment().startOf('year')
        let twoYr = moment().startOf('day').add(1, 'day');

        setTimeFilterStart(today.toDate());
        setTimeFilterEnd(twoYr.toDate());

        setQueryParams({
            limit: 25,
            ProjectionExpression: "Name, Start, Channel, Program, ContentGroup, Profile, Status, Description, SourceVideoUrl, Created, EdlLocation, HlsMasterManifest, Id, BootstrapTimeInMinutes, AudioTracks, DurationMinutes, GenerateOptoClips, GenerateOrigClips, TimecodeSource",
            timeFilterStart: moment(today.toDate()).utc().format("YYYY-MM-DDTHH:mm:ss") + "Z",
            timeFilterEnd: moment(twoYr.toDate()).utc().format("YYYY-MM-DDTHH:mm:ss") + "Z",
        })

    }, []);

    const handleDetailsView = (row) => {
        navigate("/viewEvent", {state: {
                back: {
                    name: "Events List",
                    link: "/listEvents"
                },
                data: row
            }
        });
    };

    const getRow = (row) => {
        return [
            <TableCell align="left">
                {row.Start && moment(row.Start).format('MM/DD/YYYY h:mm:ss a (UTCZ)')}
            </TableCell>,
            <TableCell align="left">{row.Program}</TableCell>,
            <TableCell align="left">
                <Button color={"primary"} onClick={() => {
                    handleDetailsView(row)
                }}>
                    {row.Name}
                </Button>
            </TableCell>,
            <TableCell align="left">{row.Channel || "-"}</TableCell>,
            <TableCell align="left">{row.DurationMinutes}</TableCell>,
            <TableCell align="left">{row.Status}</TableCell>
        ]
    }

    const handleContentGroupChange = (e) => {
        let contentGroupEvent = _.get(e, 'target.value');
        setContentGroup(contentGroupEvent);
        let queryParamsCopy = queryParams;

        if (contentGroupEvent === "ALL") {
            delete queryParamsCopy["ContentGroup"]
        }
        else {
            queryParamsCopy["ContentGroup"] = contentGroupEvent;
        }

        setQueryParams(queryParamsCopy);
    }

    const handleProgramChange = (e) => {
        let selectedProgram = _.get(e, 'target.value');
        setProgram(selectedProgram);
        let queryParamsCopy = queryParams;

        if (selectedProgram === "ALL") {
            delete queryParamsCopy["Program"]
        }
        else {
            queryParamsCopy["Program"] = selectedProgram;
        }

        setQueryParams(queryParamsCopy);
    }

    const handleStartTimeChange = (filterName, dateTime) => {
        let queryParamsCopy = _.cloneDeep(queryParams);
        queryParamsCopy[filterName] = moment(dateTime).utc().format("YYYY-MM-DDTHH:mm:ss") + "Z";
        setTimeFilterStart(queryParamsCopy[filterName])
        setQueryParams(queryParamsCopy);
    };

    const handleEndTimeChange = (filterName, dateTime) => {
        let queryParamsCopy = _.cloneDeep(queryParams);
        queryParamsCopy[filterName] = moment(dateTime).utc().format("YYYY-MM-DDTHH:mm:ss") + "Z";
        setTimeFilterEnd(queryParamsCopy[filterName])
        setQueryParams(queryParamsCopy);
    };

    return (
        <ListRenderer
            fetchPath={`event/all`}
            queryParams={queryParams}
            backendPagination={true}
            getRow={getRow}
            createLink={"/addEvent"}
            header={{
                title: "Event List",
                addTooltip: "Add new Event",
                parentFilters: "events",
                filterHandlers: {
                    onContentGroupChange: handleContentGroupChange,
                    selectedContentGroup: contentGroup,
                    onProgramChange: handleProgramChange,
                    selectedProgram: program,
                    timeFilterStart: timeFilterStart,
                    onStartTimeFilterChange: handleStartTimeChange,
                    timeFilterEnd: timeFilterEnd,
                    onEndTimeFilterChange: handleEndTimeChange
                },
                hideRemoveFilters: true
            }}
            tableHeaders={[
                <TableCell align="left" style={{minWidth: 180}}>Start Time</TableCell>,
                <TableCell align="left">Program Name</TableCell>,
                <TableCell align="left">Event</TableCell>,
                <TableCell align="left">Channel</TableCell>,
                <TableCell align="left">Duration (minutes)</TableCell>,
                <TableCell align="left">Status</TableCell>,
                <TableCell align="left">Actions</TableCell>
            ]}
            emptyTableMessage={<>You don't have any events scheduled yet. <Link href="https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/guides/MRE-Developer-Guide-Events.md" target="_blank">Learn more</Link> about creating an
                Event in MRE.</>}
            rows={{
                actions: {
                    delete: {
                        path: `event/#Name/program/#Program`, //replace #Name and #Program with row.Name and row.Program in child,
                        tooltip: "Delete Event"
                    },
                    Edl: {
                        path: `event/#Name/edl/program/#Program/track/#Track`, //replace #Name and #Program with row.Name and row.Program in child,
                        tooltip: "Export to EDL",
                        showAudioTrackDialog: true
                    },
                    Hls: {
                        path: `event/#Name/hls/eventmanifest/program/#Program/track/#Track`, //replace #Name and #Program with row.Name and row.Program in child,
                        tooltip: "Export to HLS",
                        showAudioTrackDialog: true
                    },
                    downloadMetadata: {
                        tooltip: "Download Event data",
                        path: `event/#Name/export/data/program/#Program`,
                        showAudioTrackDialog: false
                    }
                }
            }}
            searchEnabled={false}
        />
    );
}