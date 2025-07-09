/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {TableCell,} from "@material-ui/core";
import {PROMPT_SUMMARY_FORM} from "../../common/Constants";
import Link from "@material-ui/core/Link";
import {ListRenderer} from "../../components/ListRenderer/ListRenderer";
import {useNavigate} from "react-router-dom";
import Button from "@material-ui/core/Button";
import _ from "lodash";
import moment from "moment";


export const PromptList = () => {
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
            </TableCell>,
            <TableCell align="left">{version.Description}</TableCell>,
            <TableCell align="left">{ moment(version.Created).format('MM/DD/YYYY')}</TableCell>,
            <TableCell align="left" style={{minWidth: 150}}>{version.Enabled ? "Yes" : "No"}</TableCell>,
            <TableCell align="left" style={{minWidth: 150}}>{version.ContentGroups.join(", ")}</TableCell>
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
        navigate("/viewPrompt",
            {state: {
                back: {
                    name: "Prompts List",
                    link: "/listPrompts"
                },
                data: row,
                inputFieldsMap: PROMPT_SUMMARY_FORM
            },

        });
    };

    return (
        <ListRenderer
            fetchPath={'prompt/all'}
            defaultTableSort={sortTableByName}
            getRow={getRow}
            getExpandableRow={getExpandableRow}
            createLink={"/addPrompt"}
            header={{
                title: "Prompt List",
                addTooltip: "Add new Prompt",
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
                <TableCell align="left">Created</TableCell>,
                <TableCell align="left">Enabled</TableCell>,
                <TableCell align="left">Content Groups</TableCell>,
                <TableCell align="left">Actions</TableCell>
            ]}
            emptyTableMessage={<>You don't have any Prompts created yet. <Link href="https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/guides/MRE-Developer-Guide-Prompts.md" target="_blank">Learn more</Link> about Prompts in MRE.</>}
            rows={{
                actions: {
                    delete: {
                        path: `prompt/#Name`, //replace #Name with row.Name in child,
                        tooltip: "Delete Prompt"
                    },
                    addVersion: {
                        link: "/addPrompt",
                    }
                },
                versions: {
                    getVersionsPath: `prompt/#Name/version/all`,
                    deleteVersionPath: `prompt/#Name/version`
                },
                isExpandable: true
            }}
        />
    );
};