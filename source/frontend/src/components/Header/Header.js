/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import clsx from 'clsx';

import logo from '../../assets/company-logo.svg';
import config from '../../config';

import {makeStyles} from "@material-ui/core/styles";
import {useNavigate} from "react-router-dom";

import Link from "@material-ui/core/Link";
import Popover from "@material-ui/core/Popover";
import Person from "@material-ui/icons/Person";
import AppBar from "@material-ui/core/AppBar";
import Toolbar from "@material-ui/core/Toolbar";
import IconButton from '@material-ui/core/IconButton';
import Drawer from '@material-ui/core/Drawer';
import List from '@material-ui/core/List';
import Divider from '@material-ui/core/Divider';
import ChevronLeftIcon from '@material-ui/icons/ChevronLeft';
import ListItem from '@material-ui/core/ListItem';
import ListItemText from '@material-ui/core/ListItemText';
import ListItemIcon from '@material-ui/core/ListItemIcon';
import Typography from "@material-ui/core/Typography";
import Button from "@material-ui/core/Button";


const drawerWidth = 240;

const useStyles = makeStyles((theme) => ({
    header: {
        color: theme.palette.layout.contrastText,
        backgroundColor: theme.palette.layout.main,
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        padding: 0
    },
    drawerPaper: {
        position: 'relative',
        whiteSpace: 'nowrap',
        width: drawerWidth,
        transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
        }),
        backgroundColor: theme.palette.secondary.main,
        color: theme.palette.secondary.contrastText,
        '& svg': {
            color: theme.palette.secondary.contrastText,
        },
        '& ul': {
            marginLeft: '16px'
        },
    },
    drawerPaperClose: {
        overflowX: 'hidden',
        transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
        }),
        width: theme.spacing(7),
        [theme.breakpoints.up('sm')]: {
            width: theme.spacing(9),
        },
    },
    menuButton: {
        marginRight: 36,
    },
    toolbar: {
        paddingRight: 24, // keep right padding when drawer closed
        '& > *': {
            marginLeft: '25px',
            marginRight: '25px',
        }
    },
    toolbarIcon: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        padding: '0 8px',
        ...theme.mixins.toolbar,
    },
    title: {
        flexGrow: 1
    },
    button: {
        color: theme.palette.secondary.contrastText
    },
    typography: {
        padding: theme.spacing(2),
        backgroundColor: theme.palette.secondary.contrastText
    }
}));

export const Header = (props) => {
    const classes = useStyles();
    const [openDrawer, setOpenDrawer] = React.useState(false);
    const [anchorEl, setAnchorEl] = React.useState(null);

    const navigate = useNavigate();

    const handleDrawerClose = () => {
        setOpenDrawer(false);
    };

    const handleUserClick = event => {
        setAnchorEl(anchorEl ? null : event.currentTarget);
    };

    const handleUserClose = () => {
        setAnchorEl(null);
    };

    const openUser = Boolean(anchorEl);

    const shouldShowMenu = menu => {
        return Array.isArray(menu) && menu.length > 0;
    }

    const showMenuItems = menu => {
        if (!shouldShowMenu(menu)) return null;

        return menu.map(item =>
            <ListItem key={item.text} component="a" button href={item.href}>
                {item.icon &&
                <ListItemIcon>
                    {item.icon}
                </ListItemIcon>
                }
                <ListItemText primary={item.text}/>
            </ListItem>
        );
    }

    const showUserMenu = (isLoggedIn, loginName, menu, onLogout) => {
        if (isLoggedIn) {
            return (
                <>
                    <span style={{marginRight: 0}}>{loginName}</span>
                    <div>
                        <IconButton style={{ color: 'rgb(212, 218, 218)' }} onClick={handleUserClick}>
                            <Person/>
                        </IconButton>
                        <Popover
                            id="userMenu"
                            open={openUser}
                            anchorEl={anchorEl}
                            onClose={handleUserClose}
                            anchorOrigin={{
                                vertical: 'bottom',
                                horizontal: 'center',
                            }}
                            transformOrigin={{
                                vertical: 'top',
                                horizontal: 'center',
                            }}
                        >
                            {onLogout &&
                            <Typography className={classes.typography}>
                                <Link 
                                        component="button"
                                        onClick={onLogout}>
                                    Logout
                                </Link>
                            </Typography>
                            }
                        </Popover>
                    </div>
                </>
            )
        }
        else return null;
    }

    const goHome = () => {
        navigate("/home");
    }

    const {loginName, menu, onLogout} = props;
    const hideLoginComponent = (loginName === undefined || loginName === null);
    const isLoggedIn = !!loginName;

    return (
        <>
            {/*@todo configurable 3 modes, static default */}
            <AppBar position={"static"} className={classes.header}>
                <Toolbar className={classes.toolbar}>
                    <Button onClick={goHome} startIcon={<img src={logo} height={"25"} alt={config.CUSTOMER_NAME}/>}/>

                    <Typography color="inherit" className={classes.title}>
                        {config.APP_TITLE}
                    </Typography>
                    {!hideLoginComponent &&
                    <>
                        {showUserMenu(isLoggedIn, loginName, menu, onLogout)}
                    </>
                    }
                </Toolbar>
            </AppBar>
            {shouldShowMenu(menu) &&
            <Drawer
                open={openDrawer}
                classes={{
                    paper: clsx(classes.drawerPaper, !openDrawer && classes.drawerPaperClose),
                }}
            >
                <div className={classes.toolbarIcon}>
                    <IconButton color={"primary"} onClick={handleDrawerClose}>
                        <ChevronLeftIcon/>
                    </IconButton>
                </div>
                <Divider/>
                <List>{showMenuItems(menu)}</List>
            </Drawer>
            }
        </>
    );
};