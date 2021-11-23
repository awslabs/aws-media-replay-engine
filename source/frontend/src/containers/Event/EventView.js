/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {useHistory} from "react-router-dom";
import {makeStyles} from '@material-ui/core/styles';

import _ from "lodash";
import Grid from "@material-ui/core/Grid";
import {
    Backdrop,
    Breadcrumbs,
    Card,
    CardContent, CardMedia, CircularProgress,
    Table, TableBody,
    TableCell, TableContainer, TableHead, TablePagination,
    TableRow, Tooltip,
    Typography
} from "@material-ui/core";
import Link from "@material-ui/core/Link";
import {EventStatsCard} from "./EventStatsCard";
import moment from "moment";
import momentDurationFormatSetup from "moment-duration-format";
import AutorenewIcon from "@material-ui/icons/Autorenew";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import IconButton from "@material-ui/core/IconButton";
import {ProfileViewDialog} from "../Profile/ProfileViewDialog";


momentDurationFormatSetup(moment);

const CLIPS_LIMIT = 25;

const useStyles = makeStyles((theme) => ({
    content: {
        marginTop: 'auto',
        flexGrow: 1,
    },
    cardContainer: {
        padding: 0
    },
    container: {
        maxHeight: "57vh"
    },
    iconSize: {
        fontSize: "26px",
        marginBottom: 3,
        color: "white"
    },
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },
}));

export const EventView = () => {
    const classes = useStyles();
    const preventDefault = (event) => event.preventDefault();
    const history = useHistory();

    const [rows, setRows] = React.useState(undefined);
    const [allClips, setAllClips] = React.useState({});
    const [shouldRefresh, setShouldRefresh] = React.useState(true);
    const [rowsPerPage, setRowsPerPage] = React.useState(CLIPS_LIMIT);
    const [page, setPage] = React.useState(0);
    const [profileViewDialogOpen, setProfileViewDialogOpen] = React.useState(false);
    const [profileClassifierState, setProfileClassifierState] = React.useState(undefined);
    const [selectedProfile, setSelectedProfile] = React.useState(false);
    const [nextToken, setNextToken] = React.useState(undefined);
    const [lastPage, setLastPage] = React.useState(0);

    const {query, isLoading} = APIHandler();

    const stateParams = _.get(history, 'location.state');
    const eventData = _.get(stateParams, 'data')

    const goBack = () => {
        history.push({pathname: "/listEvents"});
    };

    if (!stateParams) {
        goBack();
    }

    const handleProfileViewDialogClose = () => {
        setProfileViewDialogOpen(false);
    }

    const handleProfileClick = (profileName) => {
        setSelectedProfile(profileName);
        setProfileViewDialogOpen(true);
    }


    React.useEffect(() => {
        (async () => {
            let res = await fetchData();
            setAllClips(res)
        })();
    }, [shouldRefresh]);

    React.useEffect(() => {
        (async () => {
            setRows(getTableRows(allClips));
        })();
    }, [allClips]);

    const fetchData = async () => {
        let retVal;

        let profileRes = await query('get', 'api', `profile/${eventData.Profile}`, {shouldContinueLoading: true});
        let profileClassifier = _.get(profileRes, 'data.Classifier.Name');
        setProfileClassifierState(profileClassifier);

        if (profileClassifier) {
            let response = await query('get', 'api-data-plane', `event/${eventData.Name}/program/${eventData.Program}/profileClassifier/${profileClassifier}/track/1/segments/v2`,
                {
                    limit: CLIPS_LIMIT
                }
            );

            retVal = _.get(response, 'data.Segments');
            setNextToken(response.LastEvaluatedKey ? JSON.stringify(response.LastEvaluatedKey) : "");
        }

        return retVal;
    };

    const fetchMoreData = async () => {
        let res = await query('get', 'api-data-plane', `event/${eventData.Name}/program/${eventData.Program}/profileClassifier/${profileClassifierState}/track/1/segments/v2`,
            {
                limit: CLIPS_LIMIT,
                "LastEvaluatedKey": nextToken
            }
        );

        if (res.success) {
            setAllClips(allClips.concat( _.get(res, 'data.Segments')));
            setRows(rows.concat(getTableRows( _.get(res, 'data.Segments'))));
            setNextToken(res.LastEvaluatedKey ? JSON.stringify(res.LastEvaluatedKey) : "");

            if (!res.LastEvaluatedKey) {
                setLastPage(page + 1)
            }
        }
    };

    const handleRefresh = async () => {
        setShouldRefresh(!shouldRefresh);
    };

    const handleChangePage = async (event, newPage) => {
        const rowsSize = _.size(rows);

        if (rowsSize > 0 && (newPage >= (rowsSize / rowsPerPage))) {
            await fetchMoreData();
            setPage(page + 1);
        }
        else {
            setPage(newPage);
        }
    };

    const handleChangeRowsPerPage = (event) => {
        setRowsPerPage(+event.target.value);
        setPage(0);
    };

    const handleDetailsView = (clipInfo, clips) => {
        history.push({
            pathname: "/clipPreview", state: {
                back: {
                    name: "View Event",
                    link: "/viewEvent"
                },
                clipdata: clipInfo,
                allClipsData: clips,
                origEventData: eventData,
                mode: 'EventClips'
            }
        });
    };

    const getTimeRemainingDuration = () => {
        let retVal;

        let now = moment().utc();
        let startTime = moment(eventData.Start).utc();
        let timeDiff = moment.duration(startTime.diff(now));

        if (startTime.isAfter(now)) {
            retVal = moment.duration(timeDiff, 'millisecond').format('d [days], h [hours], m [minutes], s [seconds]');
        }
        else {
            retVal = "Expired";
        }

        return retVal;
    };

    const navigateToReplay = (eventName, eventProgram) => {
        history.push({
            pathname: "/listReplays", state: {
                eventFilter: eventName,
                programFilter: eventProgram,
            }
        });
    };

    const getTableRows = (rows) => {
        return (
            _.map(rows, (row) => {
                return (
                    <TableRow hover onClick={() => {
                        handleDetailsView(row, allClips)
                    }}>
                        <TableCell align="left" style={{width: 270}}>
                            <Card style={{height: 130, width: 230, padding: 0}}>
                                <CardMedia
                                    component="img"
                                    image={row.OriginalThumbnailLocation}/>
                            </Card>
                        </TableCell>
                        <TableCell align="left">{row.StartTime}</TableCell>
                        <TableCell align="left">{row.Label}</TableCell>
                        <TableCell align="left">{row.OrigLength}</TableCell>
                    </TableRow>
                )
            })
        );
    }
    if (!stateParams) {
        return (<></>);
    }
    else
        return (
            <>

                {selectedProfile && <ProfileViewDialog
                    onProfileViewDialogClose={handleProfileViewDialogClose}
                    open={profileViewDialogOpen}
                    profileName={selectedProfile}
                />}
                <Grid container direction="column" spacing={3} className={classes.content}>
                    <Grid item>
                        <Breadcrumbs>
                            <Link
                                style={{padding: 0}}
                                color="inherit"
                                component="button"
                                variant="subtitle2"
                                onClick={goBack}
                            >
                                {stateParams.back.name}
                            </Link>
                            <Typography color="textPrimary">{stateParams.data.Name}</Typography>
                        </Breadcrumbs>
                    </Grid>
                    <Grid item container direction="column" spacing={3}>
                        <Grid item container direction="row" justify="space-between">
                            <Grid item>
                                <Grid container item direction="row" spacing={2}>
                                    <Grid item>
                                        <Typography variant="h1">{stateParams.data.Name}</Typography>
                                    </Grid>
                                </Grid>
                            </Grid>
                            <Grid item>
                                <IconButton size="small" onClick={handleRefresh}>
                                    <Tooltip title="Refresh">
                                        <AutorenewIcon className={classes.iconSize}/>
                                    </Tooltip>
                                </IconButton>
                            </Grid>
                        </Grid>
                        <Grid item container direction="row" justify="space-between" spacing={1}>
                            <Grid container item direction="column" xs={2} spacing={2}>
                                <Grid item>
                                    <EventStatsCard statValue={eventData.Status} statKey={"Status"}/>
                                </Grid>
                                <Grid item>
                                    <EventStatsCard statValue={_.size(rows)} statKey={"Clips"}/>
                                </Grid>
                                <Grid item>
                                    <EventStatsCard statValue={getTimeRemainingDuration()}
                                                    statKey={"Time Remaining"}/>
                                </Grid>
                                <Grid item>
                                    <EventStatsCard statValue={"-"} statKey={"Avg Latency"}/>
                                </Grid>
                                <Grid item>
                                    <EventStatsCard statValue={"-"} statKey={"Processing Errors"}/>
                                </Grid>
                            </Grid>
                            <Grid container item direction="column" xs={8}>
                                <Card style={{paddingBottom: 0}}>
                                    <CardContent className={classes.cardContainer}>
                                        <Grid item container direction="column" spacing={3}>
                                            <Grid item>
                                                <Typography variant="h2" style={{paddingRight: 5, paddingLeft: 5}}>Clips Detected</Typography>
                                            </Grid>
                                            <Grid item>
                                                <>
                                                    <TableContainer className={classes.container}>
                                                        <Table aria-label="clips table">
                                                            <TableHead>
                                                                <TableRow>
                                                                    <TableCell align="left">Thumbnail</TableCell>
                                                                    <TableCell align="left" style={{minWidth: 150}}>Start
                                                                        Time (seconds)</TableCell>
                                                                    <TableCell align="left">Label</TableCell>
                                                                    <TableCell align="left"
                                                                               style={{minWidth: 130}}>Length
                                                                        (seconds)</TableCell>
                                                                </TableRow>
                                                            </TableHead>
                                                            <TableBody>
                                                                {isLoading === false ? rows && rows.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage) :
                                                                    <div>
                                                                        <Backdrop open={true}
                                                                                  className={classes.backdrop}>
                                                                            <CircularProgress color="inherit"/>
                                                                        </Backdrop>
                                                                    </div>
                                                                }
                                                            </TableBody>
                                                        </Table>
                                                    </TableContainer>
                                                    <TablePagination
                                                        component="div"
                                                        labelDisplayedRows={() => {
                                                            return rows &&
                                                                `Page: ${page + 1} (${page * CLIPS_LIMIT + 1} - ${_.size(rows.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)) + page * CLIPS_LIMIT}), Total Results: ${_.size(rows)}${!nextToken && page === lastPage ?
                                                                    ", No more results" : ""}`
                                                        }}
                                                        rowsPerPageOptions={[CLIPS_LIMIT]}
                                                        rowsPerPage={rowsPerPage}
                                                        page={page}
                                                        onChangePage={handleChangePage}
                                                        onChangeRowsPerPage={handleChangeRowsPerPage}
                                                        nextIconButtonProps={{
                                                            style: {
                                                                visibility: !nextToken && page === lastPage ? "hidden" : "visible"
                                                            }
                                                        }}
                                                    />
                                                    {
                                                        _.isEmpty(rows) && isLoading === false &&
                                                        <Grid container direction="row" item justify="center">
                                                            <Typography variant={"h6"}>
                                                                No clips detected for this Event.
                                                            </Typography>
                                                        </Grid>
                                                    }
                                                </>
                                            </Grid>
                                        </Grid>
                                    </CardContent>
                                </Card>
                            </Grid>
                            <Grid container item direction="column" xs={2}>
                                <Card>
                                    <CardContent className={classes.cardContainer}>
                                        <Grid container direction="column" spacing={3}>
                                            {eventData.Channel &&
                                            <Grid item>
                                                <Typography variant="subtitle2">Channel:</Typography>
                                                <Typography>{eventData.Channel}</Typography>
                                            </Grid>
                                            }
                                            {eventData.SourceVideoUrl &&
                                            <Grid item>
                                                <Typography variant="subtitle2">SourceVideoUrl:</Typography>
                                                {
                                                    _.size(eventData.SourceVideoUrl) > 20 ?
                                                        <Tooltip title={eventData.SourceVideoUrl}>
                                                            <Link href={eventData.SourceVideoUrl} target="_blank">
                                                                {eventData.SourceVideoUrl.substring(0, 17) + "..."}
                                                            </Link>
                                                        </Tooltip> :
                                                        <Link href={eventData.SourceVideoUrl} target="_blank">
                                                            {eventData.SourceVideoUrl}
                                                        </Link>
                                                }
                                            </Grid>}
                                            {
                                                eventData.BootstrapTimeInMinutes && eventData.SourceVideoUrl &&
                                                <Grid item>
                                                    <Typography variant="subtitle2">Bootstrap Time
                                                        (minutes):</Typography>
                                                    <Typography>{eventData.BootstrapTimeInMinutes}</Typography>
                                                </Grid>
                                            }
                                            <Grid item>
                                                <Typography variant="subtitle2">Start Time:</Typography>
                                                <Typography>{moment(eventData.Start).format('MM/DD/YY, h:mm:ss a')}</Typography>
                                            </Grid>
                                            <Grid item>
                                                <Typography variant="subtitle2">Duration:</Typography>
                                                <Typography>{moment.duration(eventData.DurationMinutes, "minutes").format("hh:mm:ss")}</Typography>
                                            </Grid>
                                            <Grid item>
                                                <Typography variant="subtitle2">Program:</Typography>
                                                <Typography>{eventData.Program}</Typography>
                                            </Grid>
                                            <Grid item>
                                                <Typography variant="subtitle2">Profile:</Typography>
                                                <Link component="button" onClick={() => {
                                                    handleProfileClick(eventData.Profile)
                                                }}>
                                                    {eventData.Profile}
                                                </Link>
                                            </Grid>
                                            <Grid item>
                                                <Typography variant="subtitle2">Content Group:</Typography>
                                                <Typography>{eventData.ContentGroup}</Typography>
                                            </Grid>
                                            <Grid item>
                                                <Typography variant="subtitle2">Audio Tracks:</Typography>
                                                <Typography>{_.size(eventData.AudioTracks)}</Typography>
                                            </Grid>
                                            <Grid item>
                                                <Typography variant="subtitle2">Replay Requests:</Typography>
                                                <Link component="button" onClick={() => {
                                                    navigateToReplay(eventData.Name, eventData.Program)
                                                }}>
                                                    View Replays
                                                </Link>
                                            </Grid>
                                        </Grid>
                                    </CardContent>
                                </Card>
                            </Grid>
                        </Grid>
                    </Grid>
                </Grid>
            </>

        )
};