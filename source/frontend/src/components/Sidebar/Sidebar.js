/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import {makeStyles} from '@material-ui/core/styles';
import IconButton from "@material-ui/core/IconButton";
import MenuIcon from "@material-ui/icons/Menu";
import {Drawer} from "@material-ui/core";
import List from "@material-ui/core/List";
import Divider from "@material-ui/core/Divider";
import ChevronLeftIcon from "@material-ui/icons/ChevronLeft";
import ListItem from "@material-ui/core/ListItem";
import ListItemText from "@material-ui/core/ListItemText";
import clsx from "clsx";
import Typography from "@material-ui/core/Typography";
import _ from "lodash";
import {useNavigate} from "react-router-dom";
import {SIDEBAR_ITEMS} from "../../common/Constants";


const useStyles = makeStyles((theme) => ({
    sidebar: {
        padding: theme.spacing(8, 2),
        color: theme.palette.secondary.contrastText,
        backgroundColor: theme.palette.secondary.main,
        zIndex: 1,
        width: 60,
        height: "100vh",
        position: 'absolute',
    },
    menuButton: {
        marginRight: theme.spacing(2)
    },
    drawerPaper: {
        padding: theme.spacing(8, 2),
        zIndex: 1,
        position: 'absolute',
        height: "100vh",
        width: 240,
        backgroundColor: theme.palette.secondary.main,
        color: theme.palette.secondary.contrastText,
        '& svg': {
            color: theme.palette.secondary.contrastText,
        },
        borderRight: "none",
    },
    drawerPaperClose: {
        overflowX: 'hidden',
        width: theme.spacing(7),
        [theme.breakpoints.up('sm')]: {
            width: theme.spacing(9),
        },
    },
    toolbarIcon: {
        display: 'flex',
        alignItems: 'center'
    },
    hide: {
        display: "none"
    },
}));


export const Sidebar = (props) => {
    const classes = useStyles();
    const [menuItemName, setMenuItemName] = React.useState(undefined)
    const navigate = useNavigate();

    React.useEffect(() => {
        let sidebar_item = _.find(SIDEBAR_ITEMS, item => {
            return _.includes(item.url, navigate.pathname);
        });
        if (sidebar_item) {
            setMenuItemName(sidebar_item.name);
        }
    }, [menuItemName]);


    const handleMenuItemSelect = (menuItem) => {
        menuItem.navigate();
        setMenuItemName(menuItem);
    }

    const showMenuItems = menu => {
        return _.map(menu, item => {
            return <ListItem key={item.text} button onClick={() => (handleMenuItemSelect(item))}>
                {
                    item.text === menuItemName ?
                        <ListItemText primary={item.text}>
                        </ListItemText>
                        :
                        <ListItemText secondary={item.text}>
                        </ListItemText>
                }
            </ListItem>
        });
    }

    return (
        <div className={classes.sidebar}>
            {!props.open ?
                <IconButton
                    color="inherit"
                    aria-label="open drawer"
                    onClick={props.handleDrawerOpen}
                    edge="start"
                    className={clsx(classes.menuButton, props.open && classes.hide)}
                >
                    <MenuIcon/>
                </IconButton> :

                <Drawer
                    variant="persistent"
                    anchor="left"
                    open={props.open}
                    classes={{paper: classes.drawerPaper}}
                >
                    <div className={classes.toolbarIcon}>
                        <Typography variant="subtitle2" noWrap>
                            Media Replay Engine
                        </Typography>
                        <IconButton color={"primary"} onClick={props.handleDrawerClose}>
                            <ChevronLeftIcon/>
                        </IconButton>
                    </div>
                    <Divider light/>
                    <List>{showMenuItems(props.menu)}</List>
                </Drawer>
            }
        </div>
    );
};