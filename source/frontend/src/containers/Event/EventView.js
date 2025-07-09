/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {useNavigate, useLocation} from "react-router-dom";
import {makeStyles} from '@material-ui/core/styles';

import _ from "lodash";
import config from '../../config';
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
import { ChatWindow } from '../../components/Chat/ChatWindow';
import moment from "moment";
import momentDurationFormatSetup from "moment-duration-format";
import AutorenewIcon from "@material-ui/icons/Autorenew";
import InfoIcon from '@material-ui/icons/Info';
import CloseIcon from '@material-ui/icons/Close';
import {APIHandler} from "../../common/APIHandler/APIHandler";
import IconButton from "@material-ui/core/IconButton";
import {ProfileViewDialog} from "../Profile/ProfileViewDialog";
import Modal from '@material-ui/core/Modal';
import GenAiSearchIcon from '../../assets/genai-search-3.svg';
import { Icon } from "@material-ui/core";
import {v4 as uuidv4} from "uuid";


momentDurationFormatSetup(moment);

const CLIPS_LIMIT = 24;

const useStyles = makeStyles((theme) => ({
    content: {
        marginTop: 'auto',
        flexGrow: 1,
    },
    searchSideBar: {
        color: "#FFFFFF",
        width: "21%",
        height: "calc(100% - 64px)",
        padding: "16px 16px",
        zIndex: 1,
        position: "absolute",
        borderRight: "none",
        backgroundColor: "#17191e",
        right: 0,
        top: "64px",
    },
    eventInfoModal: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: "60%",
        margin: "auto",
    },
    eventInfoModalRow: {
        display: 'flex',
        alignItems: 'start',
        justifyContent: 'start',
        width: "100%",
        margin: "auto",
        padding: 3,
        borderBottom: "1px solid #555",
        '& div': {
            padding: 10,
            width: 300
        },
        
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
    contentWrap: {
        wordBreak: "break-word"
    }
}));

export const EventView = () => {
    const classes = useStyles();
    const preventDefault = (event) => event.preventDefault();
    const navigate = useNavigate();
    const {state} = useLocation();

    const [rows, setRows] = React.useState([]);
    const [allClips, setAllClips] = React.useState([]);
    const [shouldRefresh, setShouldRefresh] = React.useState(true);
    const [rowsPerPage, setRowsPerPage] = React.useState(CLIPS_LIMIT);
    const [page, setPage] = React.useState(0);
    const [profileViewDialogOpen, setProfileViewDialogOpen] = React.useState(false);
    const [profileClassifierState, setProfileClassifierState] = React.useState(undefined);
    const [selectedProfile, setSelectedProfile] = React.useState(false);
    const [nextToken, setNextToken] = React.useState(undefined);
    const [lastPage, setLastPage] = React.useState(0);
    const [eventInfoModalEnabled, setEventInfoModalEnabled] = React.useState(false)
    const [searchOpen, setSearchOpen] = React.useState(false)
    const [isOptimizerConfiguredInProfile, setIsOptimizerConfiguredInProfile] = React.useState(false);
    const [messages, setMessages] = React.useState([]);
    const [sessionId] = React.useState(uuidv4());

    const {query, isLoading} = APIHandler();
    
    const stateParams = state;
    const eventData = _.get(stateParams, 'data')

    const goBack = () => {
        navigate("/listEvents");
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
            let metadata = await fetchEventMetadata();
            if (metadata){
                eventData['Variables'] = metadata;
            }
            setAllClips(res)
        })();
    }, [shouldRefresh]);


    const fetchData = async () => {
        let retVal;

        let profileRes = await query('get', 'api', `profile/${eventData.Profile}`, {shouldContinueLoading: true});
        let profileClassifier = _.get(profileRes, 'data.Classifier.Name');
        setProfileClassifierState(profileClassifier);
        
        setIsOptimizerConfiguredInProfile(_.get(profileRes, 'data.Optimizer.Name') !== undefined ? true : false)

        if (profileClassifier) {
            let response = await query('get', 'api-data-plane', `event/${eventData.Name}/program/${eventData.Program}/profileClassifier/${profileClassifier}/track/1/segments/v2`,
                {
                    queryParams: 
                        {
                            limit: CLIPS_LIMIT
                        }
                }
            );

            retVal = _.get(response, 'data.Segments');
            reloadSegments(response, [])
        }

        return retVal;
    };

    const reloadSegments = (response) => {
        let segments = _.get(response, 'data.Segments');
        const token = response.LastEvaluatedKey ? JSON.stringify(response.LastEvaluatedKey) : ""
        setPage(0);
        setAllClips(segments);
        setNextToken(token);
        setRows(getTableRows(segments, token));

        if (!response.LastEvaluatedKey) {
            setLastPage(page + 1)
        }
    }

    const ingestSegments = (response) => {
        let segments = _.get(response, 'data.Segments');
        const token = response.LastEvaluatedKey ? JSON.stringify(response.LastEvaluatedKey) : ""
        setAllClips(allClips.concat(segments));
        setNextToken(token);
        setRows(getTableRows(allClips.concat(segments), token));

        if (!response.LastEvaluatedKey) {
            setLastPage(page + 1)
        }
    }

    const fetchMoreData = async () => {
        let retVal;
        let res = await query('get', 'api-data-plane', `event/${eventData.Name}/program/${eventData.Program}/profileClassifier/${profileClassifierState}/track/1/segments/v2`,
            {
                queryParams:
                {
                    limit: CLIPS_LIMIT,
                    "LastEvaluatedKey": nextToken
                }
            }
        );

        if (res.success) {
            ingestSegments(res)
            retVal = _.get(res, 'data.Segments');
        }

        return retVal
    };

    const fetchEventMetadata = async () => {
        let response = await query('get', 'api', `event/${eventData.Name}/program/${eventData.Program}/context-variables`, {disableLoader: true}, {ttl: 30000});
        if (response.data && Object.keys(response.data).length > 0) {
            return response.data;
        }
        return undefined;
    }

    const handleRefresh = async () => {
        setShouldRefresh(!shouldRefresh);
    };

    const showInfoModal = () => {
        setEventInfoModalEnabled(true);
    }
    const closeInfoModal = () => {
        setEventInfoModalEnabled(false);
    }

    const openSearchSidebar = () => {
        setSearchOpen(true);
    }
    const closeSearchSidebar = () => {
        setSearchOpen(false);
    }

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

    const handleDetailsView = (clipInfo, clips, nextToken) => {
        navigate("/clipPreview", {state: {
                back: {
                    name: "View Event",
                    link: "/viewEvent"
                },
                clipdata: clipInfo,
                allClipsData: clips,
                origEventData: eventData,
                classifier: profileClassifierState,
                clipsLimit: CLIPS_LIMIT,
                nextToken: nextToken,
                mode: 'EventClips',
                data: _.get(stateParams, 'data'),
                IsOptimizerConfiguredInProfile: isOptimizerConfiguredInProfile,
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
        navigate("/listReplays", { state: {
                eventFilter: eventName,
                programFilter: eventProgram,
            }
        });
    };

    const getBucketUrl = (eventData) => {
        return `https://s3.console.aws.amazon.com/s3/buckets/${eventData.SourceVideoBucket}?prefix=${eventData.Program}/${eventData.Name}/${eventData.Profile}/`
    }

    const getClipCaption = (eventData) => {
        if (!eventData.GenerateOrigClips && !isOptimizerConfiguredInProfile){
            return "No optimizer set. Original Clip gen disabled"
        }
        else if (!eventData.GenerateOrigClips && !eventData.GenerateOptoClips){
            return "Original, Optimized segment clip generation disabled"
        }
        else if (!eventData.GenerateOrigClips && eventData.GenerateOptoClips){
            return "Original segment clip generation disabled"
        }
    }

    const getTableRows = (allRows, nextToken) => {
        return (
            _.map(allRows, (row) => {
                return (
                    <TableRow hover onClick={() => {
                        handleDetailsView(row, allRows, nextToken)
                    }}>
                        <TableCell align="left" style={{width: 270}}>
                            {
                                !eventData.GenerateOrigClips ? // display static img when original clips are not be generated
                                !eventData.GenerateOptoClips ? // display static img when optimized clips are not be generated
                                <Card style={{height: 80, width: 230, padding: 0, textAlign: "-webkit-center"}}>
                                    

                                    <CardContent style={{padding: 2}}>
                                        <Typography variant="caption">
                                            {
                                               getClipCaption(eventData) 
                                            }
                                        </Typography>
                                    </CardContent>
                                </Card>    
                                : 
                                !isOptimizerConfiguredInProfile ?
                                    <Card style={{height: 80, width: 230, padding: 0, textAlign: "-webkit-center"}}>
                                        

                                        <CardContent style={{padding: 2}}>
                                            <Typography variant="caption">
                                                {
                                                "No Optimizer set. Original clip gen disabled."
                                                }
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                :
                                <Card style={{height: 130, width: 230, padding: 0}}>
                                <CardMedia
                                    component="img"
                                    image={row.OptimizedThumbnailLocation}/>
                                </Card>
                                :
                                <Card style={{height: 130, width: 230, padding: 0}}>
                                <CardMedia
                                    component="img"
                                    image={row.OriginalThumbnailLocation}/>
                                </Card>
                            }
                            
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
                <Grid container direction="row">
                    <Grid item xs={searchOpen ? 9 : 12}>
                        <Grid container direction="column" spacing={3}  className={classes.content}>
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
                                        { config.lambda.REACT_APP_SEARCH_LAMBDA_URL && <IconButton style={{marginRight: "5px"}} size="small" onClick={searchOpen ? closeSearchSidebar: openSearchSidebar}>
                                            <Tooltip title="Search">
                                            <Icon ><img src={GenAiSearchIcon}/></Icon>
                                            </Tooltip>
                                        </IconButton>}
                                        <IconButton size="small" onClick={showInfoModal}>
                                            <Tooltip title="Event Information">
                                                <InfoIcon className={classes.iconSize}/>
                                            </Tooltip>
                                        </IconButton>
                                        <IconButton size="small" onClick={handleRefresh}>
                                            <Tooltip title="Refresh">
                                                <AutorenewIcon className={classes.iconSize}/>
                                            </Tooltip>
                                        </IconButton>
                                    </Grid>
                                </Grid>
                                <Grid item container direction="row" justify="space-between" spacing={1}>

                                    <Grid container item direction="column" >
                                        <Card style={{paddingBottom: 0}}>
                                            <CardContent className={classes.cardContainer}>
                                                <Grid item container direction="column" spacing={3}>
                                                    <Grid item>
                                                        <Typography variant="h2" style={{paddingRight: 5, paddingLeft: 5}}>Segments detected</Typography>
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
                                                                        {isLoading === false ? rows && rows.slice(page * rowsPerPage, page * rowsPerPage + (rowsPerPage)) :
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
                                                                onPageChange={handleChangePage}
                                                                onRowsPerPageChange={handleChangeRowsPerPage}
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
                                                                        No segments detected for this Event.
                                                                    </Typography>
                                                                </Grid>
                                                            }
                                                        </>
                                                    </Grid>
                                                </Grid>
                                            </CardContent>
                                        </Card>
                                    </Grid>
                                    </Grid>
                                    </Grid>
                                        <Modal
                                            open={eventInfoModalEnabled}
                                            onClose={closeInfoModal}
                                            aria-labelledby="simple-modal-title"
                                            aria-describedby="simple-modal-description"
                                            className={classes.eventInfoModal}
                                        >
                                            <Grid container item direction="column" >
                                            <Card>
                                                <CardContent className={classes.cardContainer}>
                                                    <IconButton size="small" onClick={closeInfoModal} style={{float: "right"}}>
                                                        <Tooltip title="Close Event Information">
                                                            <CloseIcon className={classes.iconSize}/>
                                                        </Tooltip>
                                                    </IconButton>
                                                    <Grid item>
                                                        <Typography variant="subtitle1">{stateParams.data.Name}</Typography>
                                                    </Grid>
                                                    <Grid container direction="column">
                                                    <Grid container direction="row" className={classes.eventInfoModalRow}>
                                                        {eventData.Channel &&
                                                        <Grid item>
                                                            <Typography variant="subtitle2">Channel:</Typography>
                                                            <Typography>{eventData.Channel}</Typography>
                                                        </Grid>
                                                        }
                                                        {eventData.SourceVideoBucket &&
                                                        <Grid item>
                                                            <Typography variant="subtitle2">S3 Source Upload Path:</Typography>
                                                            <Link className={classes.contentWrap} href={getBucketUrl(eventData)} target="_blank">
                                                            {eventData.SourceVideoBucket}/{eventData.Program}/{eventData.Name}/{eventData.Profile}
                                                            </Link>
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
                                                        </Grid>
                                                        }
                                                        {
                                                            eventData.SourceVideoUrl &&
                                                            <Grid item>
                                                                <Typography variant="subtitle2">Bootstrap Time(minutes):</Typography>
                                                                <Typography>{eventData.BootstrapTimeInMinutes}</Typography>
                                                            </Grid>
                                                        }
                                                        </Grid>
                                                        <Grid container direction="row" className={classes.eventInfoModalRow}>
                                                        <Grid item>
                                                            <Typography variant="subtitle2">Start Time:</Typography>
                                                            <Typography>{moment(eventData.Start).format('MM/DD/YY, h:mm:ss a (UTCZ)')}</Typography>
                                                        </Grid>
                                                        <Grid item>
                                                            <Typography variant="subtitle2">Duration:</Typography>
                                                            <Typography>{moment.duration(eventData.DurationMinutes, "minutes").format("hh:mm:ss")}</Typography>
                                                        </Grid>
                                                        </Grid>
                                                        <Grid container direction="row" className={classes.eventInfoModalRow}>
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
                                                        </Grid>
                                                        <Grid container direction="row" className={classes.eventInfoModalRow}>
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
                                                        <Grid container direction="row" className={classes.eventInfoModalRow}>
                                                        <Grid item>
                                                            <Typography variant="subtitle2">Gen Original Segment clip:</Typography>
                                                            <Typography>{eventData.GenerateOrigClips ? "Yes" : "No"}</Typography>
                                                        </Grid>
                                                        <Grid item>
                                                            <Typography variant="subtitle2">Gen Optimized Segment clip:</Typography>
                                                            <Typography>{eventData.GenerateOptoClips ? "Yes" : "No"}</Typography>
                                                        </Grid>
                                                        <Grid item>
                                                            <Typography variant="subtitle2">Embedded Timecode Src:</Typography>
                                                            <Typography>{eventData.TimecodeSource === undefined ? "NOT_EMBEDDED" : eventData.TimecodeSource}</Typography>
                                                        </Grid>
                                                        </Grid>
                                                        
                                                        {eventData.Variables && 
                                                        <Grid container direction="row" className={classes.eventInfoModalRow}>
                                                            <Grid container item direction="column">
                                                            <Typography variant="subtitle2">Context Variables:</Typography>
                                                                    {_.map(eventData.Variables || {}, (value, key) => {
                                                                        return <Grid item>
                                                                            <Typography variant={"body1"} key={key}>{key}:{value}</Typography>
                                                                        </Grid>
                                                                    })}
                                                            </Grid>
                                                        </Grid>}
                                                        
                                                    </Grid>
                                                </CardContent>
                                            </Card>
                                        </Grid>
                                    </Modal>
                    </Grid>
                    
                </Grid>
                </Grid>
                {searchOpen && 
                <Grid item xs={3} className={classes.searchSideBar}>
                        <ChatWindow
                            searchContext={{...eventData, SessionId: sessionId}}
                            onClose={closeSearchSidebar}
                            messages={messages}
                            setMessages={setMessages}
                        ></ChatWindow>
                    
                    </Grid>}
            </>

        )
};