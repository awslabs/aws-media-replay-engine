/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React, {useEffect} from 'react';
import {makeStyles} from "@material-ui/core/styles";
import {
    CircularProgress,
    Collapse,
    Container,
    ListItem, ListItemText, Popover, Table, TableBody,
    TableCell,
    TableContainer, TableHead,
    TableRow,
    Tooltip
} from "@material-ui/core";
import IconButton from "@material-ui/core/IconButton";
import KeyboardArrowUpIcon from "@material-ui/icons/KeyboardArrowUp";
import KeyboardArrowDownIcon from "@material-ui/icons/KeyboardArrowDown";
import MoreHorizIcon from '@material-ui/icons/MoreHoriz';
import {createPathFromTemplate, getLatestVersion, getSortedByVersion} from "../../common/utils/utils";
import _ from "lodash";
import Grid from "@material-ui/core/Grid";
import {useNavigate} from "react-router-dom";
import ConfirmDeleteDialog from "./ConfirmDeleteDialog";
import EventTracksDialog from "./EventTracksDialog";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import DeleteIcon from '@material-ui/icons/DeleteOutline';
import List from "@material-ui/core/List";

const useStyles = makeStyles((theme) => ({
    expandableContainer: {
        overflowY: "hidden"
    }
}));

export const RowRenderer = (props) => {
    const navigate = useNavigate();
    const classes = useStyles();

    const {query, isLoading} = APIHandler();

    const [open, setOpen] = React.useState(false);
    const [actionsOpen, setActionsOpen] = React.useState(null);
    const [versions, setVersions] = React.useState([]);
    const [shouldShowDeleteAlert, setShouldShowDeleteAlert] = React.useState(false);
    const [shouldShowEdlTrackPicker, setShouldShowEdlTrackPicker] = React.useState(false);
    const [shouldShowHlsTrackPicker, setShouldShowHlsTrackPicker] = React.useState(false);
    const [shouldShowDeleteWithVersionAlert, setShouldShowDeleteWithVersionAlert] = React.useState(false);
    const [versionToDelete, setVersionToDelete] = React.useState(undefined);
    const [shouldDisableEdlAction, setShouldDisableEdlAction] = React.useState(undefined);
    const [shouldDisableHlsAction, setShouldDisableHlsAction] = React.useState(undefined);

    const actionsOpenProp = Boolean(actionsOpen);
    const id = actionsOpen ? 'simple-popover' : undefined;

    useEffect(() => {
        shouldDisableEdlActionCheck();
        shouldDisableHlsActionCheck();
    }, []);

    const handleExpandRow = async () => {
        setOpen(!open)
        let response = await query('get', 'api', createPathFromTemplate(_.get(props, "versions.getVersionsPath"), props.rowData));
        let sortedResponses = getSortedByVersion(response.data);
        setVersions(sortedResponses);
    }

    // get all versions and move to create page with latest version state
    const handleAddVersion = async () => {
        let addVersionPath = createPathFromTemplate(_.get(props, "versions.getVersionsPath"), props.rowData);
        let response = await query('get', 'api', addVersionPath);
        let latestVersion = getLatestVersion(response.data);
        navigate(_.get(props, "actions.addVersion.link"), {state: latestVersion});
    };

    const handleDeleteVersion = async (version) => {
        let deleteVersionPath = createPathFromTemplate(_.get(props, "versions.deleteVersionPath"), props.rowData) + "/" + version

        await query('del', 'api', deleteVersionPath);
        let response = await query('get', 'api', createPathFromTemplate(_.get(props, "versions.getVersionsPath"), props.rowData));
        let sortedResponses = getSortedByVersion(response.data);
        setVersions(sortedResponses)

    };

    const getRowActions = () => {
        let retVal = []

        if (props.actions.addVersion) {
            retVal.push(
                <ListItem button onClick={handleAddVersion}>
                    <ListItemText primary="Add Version"/>
                </ListItem>
            )
        }
        if (props.actions.delete) {
            retVal.push(
                <ListItem button onClick={() => {
                    setShouldShowDeleteAlert(true)
                }}>
                    <ListItemText primary="Delete"/>
                </ListItem>
            )
        }
        if (props.actions.viewDetails) {
            retVal.push(
                <ListItem button onClick={() => {
                    props.methods.handleDetailsView(props.rowData)
                }}>
                    <ListItemText primary={props.actions.viewDetails.tooltip}/>
                </ListItem>
            )
        }
        if (props.actions.clipPreview) {
            retVal.push(
                <ListItem button onClick={() => {
                    props.methods.handleClipPreview(props.rowData)
                }}>
                    <ListItemText primary="View Replay Clips"/>
                </ListItem>
            );
        }
        if (props.actions.Edl) {
            retVal.push(
                <ListItem button
                          disabled={shouldDisableEdlAction}
                          onClick={() => {
                              exportEdl(props.rowData)
                          }}>
                    <ListItemText primary="Export EDL"/>
                </ListItem>
            );
        }
        if (props.actions.Hls) {
            retVal.push(
                <ListItem button
                          disabled={shouldDisableHlsAction}
                          onClick={() => {
                              exportHls(props.rowData)
                          }}
                >
                    <ListItemText primary="Export HLS"/>
                </ListItem>
            );
        }
        if (props.actions.exportMetadata) {
            retVal.push(
                <ListItem button onClick={() => {

                }}>
                    <ListItemText primary={props.actions.exportMetadata.tooltip}/>
                </ListItem>
            );
        }
        if (props.actions.downloadMetadata) {
            retVal.push(<ListItem button onClick={() => {
                downloadExportData(props.rowData)
                }}>
                    <ListItemText primary={props.actions.downloadMetadata.tooltip} />
                </ListItem>
            );
        }

        return retVal;
    };

    const shouldDisableEdlActionCheck = () => {
        if (_.get(props.rowData, 'EdlLocation') != null && _.get(props.rowData, 'EdlLocation') !== '-') {
            //When EdlLocation is a Map
            if (Object.keys(props.rowData.EdlLocation).length === 0) {
                setShouldDisableEdlAction(true);
            }
            else {
                //setShouldDisableEdlAction(props.rowData.Status === 'Complete' ? false : true);
                setShouldDisableEdlAction(false);
            }
        }
        else {
            setShouldDisableEdlAction(true);
        }
    }

    const shouldDisableHlsActionCheck = () => {
        if (props.rowData.hasOwnProperty('HlsMasterManifest')) {
            if (Object.keys(props.rowData.HlsMasterManifest).length === 0) {
                setShouldDisableHlsAction(true);
            }

            else {
                setShouldDisableHlsAction(props.rowData.Status === 'Complete' ? false : true);
            }

        }
        // For ReplayRequest
        if (props.rowData.hasOwnProperty('HlsLocation')) {
            props.rowData.HlsLocation === '-' ?
                setShouldDisableHlsAction(true) :
                setShouldDisableHlsAction(false)
        }
    }

    const exportHls = (row) => {
        setShouldShowHlsTrackPicker(props.actions.Hls.showAudioTrackDialog)
        // If Audio Track not to be displayed, export Hls for Replay
        if (!props.actions.Hls.showAudioTrackDialog) {
            props.methods.handleExportHlsReplay(row)
        }
    }

    const downloadExportData = (row) => {
        if (!props.actions.downloadMetadata.showAudioTrackDialog) {
            props.methods.handleEventDataExportDownload(row)
        }
    }

    const exportEdl = (row) => {
        setShouldShowEdlTrackPicker(props.actions.Edl.showAudioTrackDialog)
        // If Audio Track not to be displayed, export Edl for Replay
        if (!props.actions.Edl.showAudioTrackDialog) {
            props.methods.handleExportEdlReplay(row)
        }
    }

    const handleActionsClick = (event) => {
        setActionsOpen(event.currentTarget);
    };

    const handleActionsClose = () => {
        setActionsOpen(null);
    };

    return (
        <>
            {shouldShowEdlTrackPicker &&
            <EventTracksDialog setOpen={setShouldShowEdlTrackPicker}
                               open={shouldShowEdlTrackPicker}
                               resourceData={props.rowData}
                               handleEdlExport={props.methods.handleExportEdl}
                               exportType="EDL"
            />}
            {shouldShowHlsTrackPicker &&
            <EventTracksDialog setOpen={setShouldShowHlsTrackPicker}
                               open={shouldShowHlsTrackPicker}
                               resourceData={props.rowData}
                               handleEdlExport={props.methods.handleExportHls}
                               exportType="HLS"
            />}
            {shouldShowDeleteAlert &&
            <ConfirmDeleteDialog setOpen={setShouldShowDeleteAlert}
                                 open={shouldShowDeleteAlert}
                                 resourceToDelete={props.rowData}
                                 handleDelete={props.methods.handleDeleteRow}
            />}
            {shouldShowDeleteWithVersionAlert && versionToDelete &&
            <ConfirmDeleteDialog
                setOpen={setShouldShowDeleteWithVersionAlert}
                open={shouldShowDeleteWithVersionAlert}
                resourceToDelete={props.rowData}
                handleDelete={handleDeleteVersion}
                version={versionToDelete}
            />}
            <TableRow hover={props.isHover}>
                {props.isExpandable === true &&
                <TableCell>
                    <IconButton aria-label="expand row" size="small" onClick={() => {
                        handleExpandRow(props.rowData)
                    }}>
                        {open ? <KeyboardArrowUpIcon/> : <KeyboardArrowDownIcon/>}
                    </IconButton>
                </TableCell>}

                {props.getRow(props.rowData)}
                <TableCell>
                    <IconButton aria-describedby={id} color="primary" onClick={handleActionsClick}>
                        <MoreHorizIcon/>
                    </IconButton>
                    <Popover
                        id={id}
                        open={actionsOpenProp}
                        anchorEl={actionsOpen}
                        onClose={handleActionsClose}
                        anchorOrigin={{
                            vertical: 'top',
                            horizontal: 'right',
                        }}
                        transformOrigin={{
                            vertical: 'top',
                            horizontal: 'right',
                        }}
                    >
                        <List component="nav">
                            {
                                _.map(getRowActions(), action => {
                                    return action;
                                })
                            }
                        </List>
                    </Popover>
                </TableCell>
            </TableRow>
            {props.isExpandable === true &&
            <TableRow>
                <TableCell style={{paddingBottom: 0, paddingTop: 0}} colSpan={4}>
                    <Collapse in={open} timeout="auto">
                        <Container maxWidth={"large"}>
                            <Grid container direction="row">
                                <Grid item sm={10}>
                                    {isLoading ?
                                        <Container>
                                            <CircularProgress color="inherit"/>
                                        </Container> :
                                        <TableContainer className={classes.expandableContainer}>
                                            <Table size="small">
                                                <TableHead>
                                                    <TableRow>
                                                        {_.map(props.expandableHeader, header => {
                                                            return header
                                                        })}
                                                    </TableRow>
                                                </TableHead>
                                                <TableBody>
                                                    {_.map(versions, (version, index) => {
                                                        return <TableRow key={index}>
                                                            {props.getExpandableRow(version)}
                                                            <TableCell align="left" style={{minWidth: 150}}>
                                                                <Grid container direction="row" spacing={2}>
                                                                    <Grid item>
                                                                        <IconButton size="small" color="primary"
                                                                                    onClick={() => {
                                                                                        setVersionToDelete(version);
                                                                                        setShouldShowDeleteWithVersionAlert(true)
                                                                                    }}>
                                                                            <Tooltip title="Delete Version">
                                                                                <DeleteIcon/>
                                                                            </Tooltip>
                                                                        </IconButton>
                                                                    </Grid>
                                                                </Grid>
                                                            </TableCell>
                                                        </TableRow>

                                                    })}
                                                </TableBody>
                                            </Table>
                                        </TableContainer>
                                    }
                                </Grid>
                            </Grid>
                        </Container>
                    </Collapse>
                </TableCell>
            </TableRow>}
        </>
    )
}
