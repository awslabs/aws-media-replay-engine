/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React, {useEffect} from 'react';
import {useNavigate} from "react-router-dom";
import Grid from "@material-ui/core/Grid";
import {
    Backdrop,
    CircularProgress,
    Table, TableBody,
    TableContainer,
    TableHead, TablePagination,
    TableRow, Tooltip,
    Typography
} from "@material-ui/core";


import _ from "lodash";
import Box from "@material-ui/core/Box";

import {makeStyles} from "@material-ui/core/styles";
import AutorenewIcon from "@material-ui/icons/Autorenew";
import AddIcon from "@material-ui/icons/Add";
import {ContentGroupDropdown} from "../ContentGroup/ContentGroupDropdown";
import {createPathFromTemplate} from "../../common/utils/utils";
import {ProgramDropdown} from "../Programs/ProgramDropdown";
import {EventDropdown} from "../Event/EventDropdown";
import DeleteForeverIcon from "@material-ui/icons/DeleteForever";
import IconButton from "@material-ui/core/IconButton";
import {RowRenderer} from "./RowRenderer";
import {PluginClassDropdown} from "../PluginClassDropdown/PluginClassDropdown";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import {parseReplayDetails} from "../Replay/common";
import {EventFilters} from "../../containers/Event/Components/EventFilters";
import { AllEventsDropdown } from '../Event/AllEventsDropDown';


const useStyles = makeStyles((theme) => ({
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


export const ListRenderer = (props) => {
    const navigate = useNavigate();
    const classes = useStyles();

    const {query, isLoading} = APIHandler();

    let contentGroupFilterInit = _.get(props, 'header.contentGroupFilter') === true ? "ALL" : undefined;
    let pluginClassInit = _.get(props, 'header.pluginClassFilter') === true ? "ALL" : undefined;

    const [shouldRefresh, setShouldRefresh] = React.useState(true);
    const [rowsPerPage, setRowsPerPage] = React.useState(25);
    const [page, setPage] = React.useState(0);
    const [rows, setRows] = React.useState(undefined);
    const [originalTableData, setOriginalTableData] = React.useState(undefined);
    const [contentGroupFilter, setContentGroupFilter] = React.useState(contentGroupFilterInit);
    const [eventFilter, setEventFilter] = React.useState(props.eventFilterInitValue || "ALL");
    const [programFilter, setProgramFilter] = React.useState(props.programFilterInitValue || "ALL");
    const [pluginClassFilter, setPluginClassFilter] = React.useState(pluginClassInit);
    const [nextToken, setNextToken] = React.useState(undefined);
    const [lastPage, setLastPage] = React.useState(0);

    React.useEffect(() => {
        (async () => {
            await initTable();
        })();
    }, [shouldRefresh, props.queryParams]);

    //region Table
    const fetchTableData = async () => {
        return await query('get', 'api', props.fetchPath, {queryParams:props.queryParams});
    };

    const fetchReplaysByContentGroup = async (contentGroup) => {
        return await query('get', 'api', `replay/all/contentgroup/${contentGroup}`);
    };

    const fetchMoreData = async () => {
        _.set(props.queryParams, "LastEvaluatedKey", JSON.stringify(nextToken));

        let res = await query('get', 'api', props.fetchPath, props.queryParams);

        if (res.success) {
            setOriginalTableData(originalTableData.concat(res.data));
            setRows(rows.concat(res.data));
            setNextToken(res.LastEvaluatedKey);

            if (!res.LastEvaluatedKey) {
                setLastPage(page + 1)
            }
        }
    };


    const initFilters = (tableData) => {
        setContentGroupFilter(_.get(props, 'header.contentGroupFilter') === true ? "ALL" : undefined);
        if (eventFilter !== "ALL" || programFilter !== "ALL") {
            handleAllFilters(undefined, undefined, tableData);
        }
    };

    const initTable = async () => {
        let res;
        let sortedTableData;

        if (!props.backendPagination) {
            res = await fetchTableData();
            let tableData = res.data;
            tableData = _.filter(tableData, row => {
                return _.has(row, "Enabled") !== true || row.Enabled !== false;
            });
            sortedTableData = props.defaultTableSort ? props.defaultTableSort(tableData) : tableData;
        }
        else {
            if (_.isEmpty(props.queryParams) !== true) {
                res = await fetchTableData();
                sortedTableData = res.data;
                setNextToken(res.LastEvaluatedKey);
            }
        }

        if (res && res.success) {
            setOriginalTableData([...sortedTableData]);
            setRows([...sortedTableData]);
            setPage(0);
        }
        if (!props.backendPagination) {
                initFilters([...sortedTableData]);
        }

    };

    const handleRefresh = async () => {
        setShouldRefresh(!shouldRefresh);
    };

    const handleClearFilters = async () => {
        setEventFilter("ALL");
        setProgramFilter("ALL");
        setPluginClassFilter("ALL");
        setContentGroupFilter("ALL");
        handleRefresh();
    };

    const handleChangePage = async (event, newPage) => {
        const rowsSize = _.size(rows);

        if (rowsSize > 0 && (newPage >= (rowsSize / rowsPerPage)) && props.backendPagination) {
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

    //endregion

    //region Row

    const handleDetailsView = async (row) => {
        // replayDetails is the only dynamic endpoint for details view. for others, use props.
        let replaysDetailsPath = _.get(props, 'rows.actions.viewDetails.replayDetails');
        let replayDetailsParsed;

        if (replaysDetailsPath) {
            let replayDetailsPath = createPathFromTemplate(replaysDetailsPath, row);
            let replayDetails = await query('get', 'api', replayDetailsPath);
            replayDetailsParsed = parseReplayDetails(replayDetails.data, row);
        }

        navigate(props.rows.actions.viewDetails.path, {state: {
                back: {
                    name: props.rows.actions.viewDetails.name,
                    link: props.rows.actions.viewDetails.link
                },
                data: replayDetailsParsed || row,
                inputFieldsMap: _.get(props, "rows.actions.viewDetails.inputFieldsMap"),
            }
        });
    };

    const downloadBlob = (blob, filename) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename || 'download';
        const clickHandler = () => {
            setTimeout(() => {
                URL.revokeObjectURL(url);
                a.removeEventListener('click', clickHandler);
            }, 150);
        };
        a.addEventListener('click', clickHandler, false);
        a.click();
        return a;
    }

    const handleExportEdl = async (row, track) => {
        let exportPathTemplate = _.get(props, "rows.actions.Edl.path");
        let exportPath = createPathFromTemplate(exportPathTemplate, row);
        exportPath = `${exportPath}${track}`
        const result = await query('get_blob', 'api', exportPath, {disableLoader: true});
        downloadBlob(result.data, `${row.Name}-${track}.edl`);
    };

    const handleExportEdlReplay = async (row) => {
        let exportPathTemplate = _.get(props, "rows.actions.Edl.path");
        let exportPath = createPathFromTemplate(exportPathTemplate, row);
        const result = await query('get_blob', 'api', exportPath, {disableLoader: true});
        downloadBlob(result.data, `${row.Event}.edl`);
    };

    const handleEventDataExportDownload = async (row) => {
        let exportPathToolTip = _.get(props, "rows.actions.downloadMetadata.tooltip");

        let exportPathTemplate = _.get(props, "rows.actions.downloadMetadata.path");
        let exportPath = createPathFromTemplate(exportPathTemplate, row);
        const result = await query('get_blob', 'api', exportPath, {disableLoader: true});
        if (result.success)
            if (exportPathToolTip.includes('Replay'))
                downloadBlob(result.data, `${row.Event}-replay-export.json`);
            else
                downloadBlob(result.data, `${row.Name}-event-export.json`);
    };


    const handleExportHls = async (row, track) => {
        let exportPathTemplate = _.get(props, "rows.actions.Hls.path");
        let exportPath = createPathFromTemplate(exportPathTemplate, row);
        exportPath = `${exportPath}${track}`
        const result = await query('get_blob', 'api', exportPath, {disableLoader: true});
        downloadBlob(result.data, `${row.Name}-${track}-MasterManifest.m3u8`);

    };

    const handleExportHlsReplay = async (row) => {
        let exportPathTemplate = _.get(props, "rows.actions.Hls.path");
        let exportPath = createPathFromTemplate(exportPathTemplate, row);

        const result = await query('get_blob', 'api', exportPath, {disableLoader: true});
        downloadBlob(result.data, `${row.Event}-MasterManifest.m3u8`);
    };

    const handleDeleteRow = async (row) => {
        let deletePathTemplate = _.get(props, "rows.actions.delete.path");

        let deletePath = createPathFromTemplate(deletePathTemplate, row);

        await query('del', 'api', deletePath);
        await initTable();
    };

    const handleClipPreview = async (row) => {
        navigate(props.rows.actions.clipPreview.path, {state: {
                back: {
                    name: props.rows.actions.clipPreview.name,
                    link: props.rows.actions.clipPreview.link
                },
                data: row,
                mode: 'ReplayClips'
            }
        });
    }

    const handleCreate = () => {
        navigate(props.createLink, {state: {}});
    };

    const getTableRows = (tableData) => {
        return _.map(tableData, (row, index) => {
            return <RowRenderer
                rowData={row}
                actions={props.rows.actions}
                hasExport={props.rows.export}
                isExpandable={props.rows.isExpandable}
                methods={{
                    handleDetailsView,
                    handleDeleteRow,
                    handleClipPreview,
                    handleExportEdl,
                    handleExportHls,
                    handleExportEdlReplay,
                    handleExportHlsReplay,
                    handleEventDataExportDownload
                }}
                getRow={props.getRow}
                getExpandableRow={props.getExpandableRow}
                versions={props.rows.versions}
                expandableHeader={props.expandableHeader}
                handleDetail
                isHover={true}
            />

        });
    };

    //endregion

    // region Filters
    const FILTERS = {
        contentGroupFilter: {
            name: "contentGroupFilter",
            handler: (contentGroup, filteredTableData) => {
                setContentGroupFilter(contentGroup);

                if (_.lowerCase(contentGroup) !== "all") {
                    filteredTableData = _.filter(filteredTableData, item => {
                        return _.includes(item.ContentGroups, contentGroup);
                    });
                }
                setRows(filteredTableData);

                return filteredTableData;
            },
            replaysHandler: async (contentGroup) => {
                setContentGroupFilter(contentGroup);
                setEventFilter("ALL");
                setProgramFilter("ALL");

                let tableDataCopy = _.cloneDeep(originalTableData);

                if (_.lowerCase(contentGroup) !== "all") {
                    let response = await fetchReplaysByContentGroup(contentGroup);
                    tableDataCopy = response.data;
                }
                setRows(tableDataCopy);
            },
            value: contentGroupFilter
        },
        eventFilter: {
            name: "eventFilter",
            handler: (event, filteredTableData) => {
                if (event !== "Load More") {
                    setEventFilter(event);
                    if (_.lowerCase(event) !== "all") {
                        filteredTableData = _.filter(filteredTableData, item => {
                            return item.Event === event;
                        });
                    }
                    setRows(filteredTableData);
                }
                return filteredTableData;
            },
            value: eventFilter
        },
        programFilter: {
            name: "programFilter",
            handler: (program, filteredTableData) => {
                setProgramFilter(program);

                if (_.lowerCase(program) !== "all") {
                    filteredTableData = _.filter(filteredTableData, item => {
                        return item.Program === program;
                    });
                }
                setRows(filteredTableData);

                return filteredTableData;
            },
            value: programFilter
        },
        pluginClassFilter: {
            name: "pluginClassFilter",
            handler: (pluginClass, filteredTableData) => {
                setPluginClassFilter(pluginClass);

                if (_.lowerCase(pluginClass) !== "all") {
                    filteredTableData = _.filter(filteredTableData, item => {
                        return item.Class === pluginClass;
                    });
                }
                setRows(filteredTableData);

                return filteredTableData;
            },
            value: pluginClassFilter
        }
    }

    const handleAllFilters = async (currentFilterName, valueToFilterBy, tableData = originalTableData) => {
        let tableDataCopyToFilter = _.cloneDeep(tableData);
        if (props.header.replayFilter != null) {
            if (currentFilterName === FILTERS.contentGroupFilter.name) {
                await FILTERS.contentGroupFilter.replaysHandler(valueToFilterBy);
            }
            else {
                // changed by the filter
                if (!(valueToFilterBy == "Load More" && currentFilterName === FILTERS.eventFilter.name)) {
                    setContentGroupFilter("ALL");
                    if (contentGroupFilter !== "ALL") {
                        let res = await fetchTableData();
                        let tableData = res.data;
                        tableDataCopyToFilter = _.filter(tableData, row => {
                            return _.has(row, "Enabled") !== true || row.Enabled !== false;
                        });

                        if (res && res.success) {
                            setOriginalTableData(tableDataCopyToFilter);
                            setRows(tableDataCopyToFilter);
                            setPage(0);
                        }
                    }

                    if ((currentFilterName === FILTERS.eventFilter.name || currentFilterName === FILTERS.programFilter.name)) {
                        if (currentFilterName === FILTERS.eventFilter.name && programFilter !== "ALL") {
                            let dataFilteredByEvents = FILTERS.eventFilter.handler(valueToFilterBy, tableDataCopyToFilter);
                            FILTERS.programFilter.handler(programFilter, dataFilteredByEvents)
                        }
                        else if (currentFilterName === FILTERS.programFilter.name && eventFilter !== "ALL") {
                            let dataFilteredByPrograms = FILTERS.programFilter.handler(valueToFilterBy, tableDataCopyToFilter);
                            FILTERS.eventFilter.handler(eventFilter, dataFilteredByPrograms)
                        }
                        else {
                            if (currentFilterName === FILTERS.programFilter.name) {
                                FILTERS.programFilter.handler(valueToFilterBy, tableDataCopyToFilter);
                            }
                            if (currentFilterName === FILTERS.eventFilter.name) {
                                FILTERS.eventFilter.handler(valueToFilterBy, tableDataCopyToFilter);
                            }
                        }
                    }
                    // changed on initialization (called from a view event)
                    else {
                        if (eventFilter !== "ALL" && programFilter !== "ALL") {
                            let filteredEvents = FILTERS.eventFilter.handler(eventFilter, tableDataCopyToFilter);
                            FILTERS.programFilter.handler(programFilter, filteredEvents)
                        }
                        else {
                            if (programFilter !== "ALL") {
                                FILTERS.programFilter.handler(programFilter, tableDataCopyToFilter);
                            }
                            if (eventFilter !== "ALL") {
                                FILTERS.eventFilter.handler(eventFilter, tableDataCopyToFilter);
                            }
                        }

                    }
                }
            }


        }
        else {
            _.forOwn(FILTERS, (filterProps, filterName) => {
                if (filterProps.value) {
                    tableDataCopyToFilter = filterProps.handler(currentFilterName === filterName ?
                        valueToFilterBy : filterProps.value, tableDataCopyToFilter);
                }
            });
        }
    };
    // endregion

    return (
        <Grid container direction="column" spacing={4}>
            <Grid container item direction="row" justify="space-between" alignItems="center">
                <Grid item sm={2} style={{paddingTop: "3vh"}}>
                    <Typography variant="h1">
                        {props.header.title}
                    </Typography>
                </Grid>
                <Grid container item direction="row" sm={10} justify="flex-end" alignItems="flex-end" spacing={2}>
                    {props.header.parentFilters == "events" ?
                        <Grid container item direction="row" justify="flex-end" alignItems="center" spacing={1} xs={10}
                              xl={7}>
                            <EventFilters
                                onContentGroupChange={props.header.filterHandlers.onContentGroupChange}
                                afterFilterChange={initTable}
                                selectedContentGroup={props.header.filterHandlers.selectedContentGroup}
                                toFilter={props.header.filterHandlers.toFilter}
                                onTimeFilterChange={props.header.filterHandlers.onTimeFilterChange}
                            />
                        </Grid> :
                        <>
                            {props.header.pluginClassFilter &&
                                <Grid item sm={4}>
                                    <PluginClassDropdown handleChange={(e) => {
                                        handleAllFilters(FILTERS.pluginClassFilter.name, e.target.value)
                                    }}
                                                         selected={FILTERS.pluginClassFilter.value}
                                    />
                                </Grid>}
                            {props.header.contentGroupFilter &&
                                <Grid item sm={3}>
                                    <ContentGroupDropdown handleChange={(e) => {
                                        handleAllFilters(FILTERS.contentGroupFilter.name, e.target.value)
                                    }}
                                                          selected={FILTERS.contentGroupFilter.value}
                                    />
                                </Grid>}
                            {props.header.replayFilter &&
                                <Grid container item direction="row" alignItems="flex-end" spacing={2} sm={7}>
                                    <Box p={2}>
                                        <Typography variant="h2">or</Typography>
                                    </Box>
                                    <Grid item sm={3}>
                                        <ProgramDropdown
                                            handleChange={(e) => {
                                                handleAllFilters(FILTERS.programFilter.name, e.target.value)
                                            }}
                                            selected={FILTERS.programFilter.value}
                                        />
                                    </Grid>
                                    <Box p={2}>
                                        <Typography variant="h2">and</Typography>
                                    </Box>
                                    <Grid item sm={3}>
                                        <AllEventsDropdown
                                            initValue={props.eventFilterInitValue}
                                            handleChange={(e) => {
                                                handleAllFilters(FILTERS.eventFilter.name, e.target.value)
                                            }}
                                            selected={FILTERS.eventFilter.value}
                                        />
                                    </Grid>
                                </Grid>}
                        </>}
                    <Grid item container direction="row" alignItems="flex-end" justify="flex-end" sm={2}
                          spacing={1}>
                        {props.header.hideRemoveFilters !== true &&
                            <Grid item>
                                <IconButton size="small" onClick={handleClearFilters}>
                                    <Tooltip title="Clear filters">
                                        <DeleteForeverIcon className={classes.iconSize}/>
                                    </Tooltip>
                                </IconButton>
                            </Grid>
                        }

                        <Grid item>
                            <IconButton size="small" onClick={handleRefresh}>
                                <Tooltip title="Refresh">
                                    <AutorenewIcon className={classes.iconSize}/>
                                </Tooltip>
                            </IconButton>
                        </Grid>
                        <Grid item>
                            <IconButton size="small" onClick={handleCreate}>
                                <Tooltip title={props.header.addTooltip}>
                                    <AddIcon className={classes.iconSize}/>
                                </Tooltip>
                            </IconButton>
                        </Grid>
                    </Grid>

                </Grid>
            </Grid>
            <Grid item>
                {isLoading === true ?
                    <div>
                        <Backdrop open={true} className={classes.backdrop}>
                            <CircularProgress color="inherit"/>
                        </Backdrop>
                    </div> :
                    <>
                        <TableContainer className={classes.container}>
                            <Table stickyHeader>
                                <TableHead style={{tableLayout: "auto"}}>
                                    <TableRow>
                                        {_.map(props.tableHeaders, header => {
                                            return header;
                                        })}
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {getTableRows(rows?.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                        {
                            props.backendPagination ?
                                <TablePagination
                                    component="div"
                                    labelDisplayedRows={() => {
                                        return rows && props.queryParams &&
                                            `Page: ${page + 1} (${page * props.queryParams.limit + 1} - ${_.size(rows.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)) + page * props.queryParams.limit}), Total Results: ${_.size(rows)}${!nextToken && page === lastPage ?
                                                ", No more results" : ""}`
                                    }}
                                    rowsPerPageOptions={[25]}
                                    rowsPerPage={rowsPerPage}
                                    page={page}
                                    onChangePage={handleChangePage}
                                    onChangeRowsPerPage={handleChangeRowsPerPage}
                                    nextIconButtonProps={{
                                        style: {
                                            visibility: !nextToken && page === lastPage ? "hidden" : "visible"
                                        }
                                    }}
                                /> :
                                <TablePagination
                                    rowsPerPageOptions={[10, 25]}
                                    component="div"
                                    count={_.size(rows)}
                                    rowsPerPage={rowsPerPage}
                                    page={page}
                                    onChangePage={handleChangePage}
                                    onChangeRowsPerPage={handleChangeRowsPerPage}
                                />
                        }
                        {
                            rows && _.isEmpty(rows) && isLoading === false &&
                            <Box pt={3} display="flex" justifyContent="center">
                                <Typography variant={"h6"}>
                                    {props.emptyTableMessage}
                                </Typography>
                            </Box>
                        }
                    </>
                }
            </Grid>
        </Grid>
    );
}