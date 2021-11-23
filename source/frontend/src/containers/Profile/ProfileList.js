/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {TableCell, Tooltip,} from "@material-ui/core";
import _ from "lodash";
import Link from "@material-ui/core/Link";
import {PROFILE_SUMMARY_FORM} from "../../common/Constants";
import {ListRenderer} from "../../components/ListRenderer/ListRenderer";
import Button from "@material-ui/core/Button";
import {useHistory} from "react-router-dom";


export const ProfileList = () => {
    const history = useHistory();

    const sortTableByName = (tableData) => {
        return _.sortBy(tableData, item => {
            return _.lowerCase(item.Name);
        });
    };

    const getContentGroups = (row) => {
        let splitContentGroups = row.ContentGroups.join(', ');

        return (
            <div>
                {_.size(splitContentGroups) > 30 ?
                    <Tooltip title={splitContentGroups}>
                        <span>
                            {splitContentGroups.substring(0, 27) + "..."}
                        </span>
                    </Tooltip> :
                    <span>{splitContentGroups}</span>
                }
            </div>
        )
    };

    const handleDetailsView = (row) => {
        history.push({
            pathname: "/viewProfile",
            state: {
                back: {
                    name: "Profiles List",
                    link: "/listProfiles"
                },
                data: row,
                inputFieldsMap: PROFILE_SUMMARY_FORM
            },

        });
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
            <TableCell align="left">{row.Description}</TableCell>,
            <TableCell align="left">{getContentGroups(row)}</TableCell>
        ]
    }

    return (
        <ListRenderer
            fetchPath={'profile/all'}
            defaultTableSort={sortTableByName}
            getRow={getRow}
            createLink={"/addProfile"}
            header={{
                title: "Profile List",
                addTooltip: "Add new Profile",
                contentGroupFilter: true
            }}
            tableHeaders={[
                <TableCell align="left">Profile Name</TableCell>,
                <TableCell align="left">Description</TableCell>,
                <TableCell align="left">Content Groups</TableCell>,
                <TableCell align="left">Actions</TableCell>
            ]}
            emptyTableMessage={<>You don't have any Profiles created yet. <Link>Learn more</Link> about creating a
                Profile using MRE.</>}
            rows={{
                actions: {
                    delete: {
                        path: `profile/#Name`, //replace #Name with row.Name in Child
                        tooltip: "Delete Profile"
                    }
                },
            }}
        />
    );
}