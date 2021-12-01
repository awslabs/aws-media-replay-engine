/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {TableCell,} from "@material-ui/core";
import {PLUGIN_SUMMARY_FORM} from "../../common/Constants";
import Link from "@material-ui/core/Link";
import {ListRenderer} from "../../components/ListRenderer/ListRenderer";
import {useHistory} from "react-router-dom";
import Button from "@material-ui/core/Button";
import _ from "lodash";


export const PluginList = () => {
    const history = useHistory();

    const sortTableByName = (tableData) => {
        return _.sortBy(tableData, item => {
            return _.lowerCase(item.Name);
        });
    };

    const getExpandableRow = (version) => {
        return [
            <TableCell align="left" style={{minWidth: 150}}>{version.Version}</TableCell>,
            <TableCell align="left">{version.Description}</TableCell>,
            <TableCell align="left" style={{minWidth: 150}}>{version.Class}</TableCell>
        ]
    };

    const getRow = (row) => {
        return [
            <TableCell align="left">
                <Button color={"primary"} onClick={() => {
                    handleDetailsView(row)
                }}>
                    {row.Name}
                </Button>
            </TableCell>,
            <TableCell align="left">{row.Description}</TableCell>
        ]
    };

    const handleDetailsView = (row) => {
        history.push({
            pathname: "/viewPlugin",
            state: {
                back: {
                    name: "Plugins List",
                    link: "/listPlugins"
                },
                data: row,
                inputFieldsMap: PLUGIN_SUMMARY_FORM
            },

        });
    };

    return (
        <ListRenderer
            fetchPath={'plugin/all'}
            defaultTableSort={sortTableByName}
            getRow={getRow}
            getExpandableRow={getExpandableRow}
            createLink={"/addPlugin"}
            header={{
                title: "Plugin List",
                addTooltip: "Add new Plugin",
                pluginClassFilter: true,
                contentGroupFilter: true,
            }}
            tableHeaders={[
                <TableCell/>,
                <TableCell align="left">Name</TableCell>,
                <TableCell align="left">Description</TableCell>,
                <TableCell align="left">Actions</TableCell>
            ]}
            expandableHeader={[
                <TableCell align="left"># Version</TableCell>,
                <TableCell align="left">Description</TableCell>,
                <TableCell align="left">Class</TableCell>,
                <TableCell align="left">Actions</TableCell>
            ]}
            emptyTableMessage={<>You don't have any plugins created yet. <Link href="https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/guides/MRE-Developer-Guide-Plugins.md" target="_blank">Learn more</Link> about Plugin Development in MRE.</>}
            rows={{
                actions: {
                    delete: {
                        path: `plugin/#Name`, //replace #Name with row.Name in child,
                        tooltip: "Delete Plugin"
                    },
                    addVersion: {
                        link: "/addPlugin",
                    }
                },
                versions: {
                    getVersionsPath: `plugin/#Name/version/all`,
                    deleteVersionPath: `plugin/#Name/version`
                },
                isExpandable: true
            }}
        />
    );
};