/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {TableCell,} from "@material-ui/core";
import {MODEL_SUMMARY_FORM} from "../../common/Constants";
import Link from "@material-ui/core/Link";
import {ListRenderer} from "../../components/ListRenderer/ListRenderer";
import {useNavigate} from "react-router-dom";
import Button from "@material-ui/core/Button";
import _ from "lodash";


export const ModelList = () => {
    const navigate = useNavigate();

    const sortTableByName = (tableData) => {
        return _.sortBy(tableData, item => {
            return _.lowerCase(item.Name);
        });
    };

    const getExpandableRow = (version) => {
        return [
            <TableCell align="left" style={{minWidth: 150}}>
                <Button color={"primary"} onClick={() => {
                    handleDetailsView(version)
                }}>
                    {version.Version}
                </Button>
            </TableCell>,,
            <TableCell align="left">{version.Description}</TableCell>,
            <TableCell align="left">{version.Endpoint}</TableCell>,
            <TableCell align="left" style={{minWidth: 150}}>{version.PluginClass}</TableCell>
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
        navigate("/viewModel",
            {state: {
                back: {
                    name: "Models List",
                    link: "/listModels"
                },
                data: row,
                inputFieldsMap: MODEL_SUMMARY_FORM
            },

        });
    };

    return (
        <ListRenderer
            fetchPath={'model/all'}
            defaultTableSort={sortTableByName}
            getRow={getRow}
            getExpandableRow={getExpandableRow}
            createLink={"/addModel"}
            header={{
                title: "Model List",
                addTooltip: "Add new Model",
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
                <TableCell align="left">Endpoint</TableCell>,
                <TableCell align="left">Plugin Class</TableCell>,
                <TableCell align="left">Actions</TableCell>
            ]}
            emptyTableMessage={<>You don't have any Models created yet. <Link href="https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/guides/MRE-Developer-Guide-Models.md" target="_blank">Learn more</Link> about Models in MRE.</>}
            rows={{
                actions: {
                    delete: {
                        path: `model/#Name`, //replace #Name with row.Name in child,
                        tooltip: "Delete Model"
                    },
                    addVersion: {
                        link: "/addModel",
                    }
                },
                versions: {
                    getVersionsPath: `model/#Name/version/all`,
                    deleteVersionPath: `model/#Name/version`
                },
                isExpandable: true
            }}
        />
    );
};