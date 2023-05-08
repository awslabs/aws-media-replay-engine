/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import React from 'react';

import logo from '../../assets/aws-logo.svg';
import config from '../../config';

import {makeStyles} from "@material-ui/core/styles";

import Link from "@material-ui/core/Link";
import Popover from "@material-ui/core/Popover";
import Person from "@material-ui/icons/Person";
import AppBar from "@material-ui/core/AppBar";
import Toolbar from "@material-ui/core/Toolbar";
import IconButton from '@material-ui/core/IconButton';
import Typography from "@material-ui/core/Typography";

const drawerWidth = 240;

const useStyles = makeStyles((theme) => ({
    drawerPaper: {
        position: 'relative',
        whiteSpace: 'nowrap',
        width: drawerWidth,
        transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
        }),
        backgroundColor: '#232F3E',
        color: theme.palette.primary.contrastText,
        '& svg': {
            color: theme.palette.primary.contrastText,
        },
        '& ul': {
            marginLeft: '16px'
        }
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
        color: theme.palette.primary.contrastText
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
        flexGrow: 1,
        marginTop: 10,
        color: theme.palette.primary.contrastText
    },
    button: {
        color: theme.palette.primary.contrastText
    },
    typography: {
        padding: theme.spacing(2),
        backgroundColor: theme.palette.primary.contrastText
    },
    popOver: {
        color: theme.palette.primary.contrastText
    },
    personIcon: {
        color: theme.palette.primary.contrastText
    }
}));

function Header(props) {
    const classes = useStyles();
    const [anchorEl, setAnchorEl] = React.useState(null);

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

    const showUserMenu = (isLoggedIn, loginName, menu, onLogout) => {
        if (isLoggedIn) {
            return (
                <>
                    <Typography className={classes.popOver}>{loginName}</Typography>
                    <div>
                        <IconButton className={classes.personIcon} onClick={handleUserClick}>
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
                                <Link href="/login" onClick={onLogout}>
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

    const {loginName, menu, onLogout} = props;
    const hideLoginComponent = (loginName === undefined || loginName === null);
    const isLoggedIn = !!loginName;

    return (
        <AppBar position={"static"} style={{backgroundColor: "#000000"}}>
            <Toolbar className={classes.toolbar}>
                <img src={logo} height={"35"} alt={config.CUSTOMER_NAME}/>
                <Typography component="h1" variant="h6" color="inherit" noWrap
                            className={classes.title}>
                    {config.APP_TITLE}
                </Typography>
                {!hideLoginComponent &&
                <>
                    {showUserMenu(isLoggedIn, loginName, menu, onLogout)}
                </>
                }
            </Toolbar>
        </AppBar>
    );
}

export default Header;
