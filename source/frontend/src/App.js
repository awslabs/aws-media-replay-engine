/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React, {useState, useEffect} from "react";
import {withRouter, useHistory} from "react-router-dom";
import {Auth} from "aws-amplify";

import config from "./config";
import {SessionContext} from "./contexts/SessionContext";

import "./App.css";
import CssBaseline from '@material-ui/core/CssBaseline';

import {DemoContainer} from './components/Layouts/DemoContainer';
import {Header} from "./components/Header/Header";
import {Footer} from "./components/Footer/Footer";

import Routes from "./Routes";
import Grid from "@material-ui/core/Grid";
import {Sidebar} from "./components/Sidebar/Sidebar";
import Box from "@material-ui/core/Box";
import clsx from "clsx";
import {makeStyles} from "@material-ui/core/styles";
import {SnackbarContent} from "@material-ui/core";
import Button from "@material-ui/core/Button";


const useStyles = makeStyles((theme) => ({
    openSidebar: {
        width: 240,
    },
    closedSidebar: {
        width: 100,
    },
    routesWithOpenSidebar: {
        paddingLeft: 280,
        paddingRight: 40

    },
    routesWithClosedSidebar: {
        paddingLeft: 100,
        paddingRight: 40
    },
    alert: {
        width: '100%',
        '& > * + *': {
            marginTop: theme.spacing(2),
        },
        top: 50,
        position: "sticky",
        zIndex: 101
    },

}));

const App = (props) => {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [authenticatedUserName, setAuthenticatedUserName] = useState('');
    const [isAuthenticating, setIsAuthenticating] = useState(true);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [errorMessage, setErrorMessage] = useState(undefined);

    const history = useHistory();
    const classes = useStyles();

    const userHasAuthenticated = username => {
        const isAuthenticated = !!username;
        setIsAuthenticated(isAuthenticated);
        setAuthenticatedUserName(username);
    };

    useEffect(() => {
        initApp();
    }, []);

    const initApp = async () => {
        document.title = config.APP_TITLE;
        try {
            const session = await Auth.currentSession();
            if (session) {
                userHasAuthenticated(session.accessToken.payload.username);
            }
        }
        catch (e) {
            if (e !== 'No current user') {
                console.warn(e);
            }
        }
        setIsAuthenticating(false);
    };

    const handleLogout = async () => {
        await Auth.signOut();
        userHasAuthenticated(false);
        props.history.push("/login");
    };

    const handleDrawerOpen = () => {
        setIsSidebarOpen(true);
    };

    const handleDrawerClose = () => {
        setIsSidebarOpen(false);
    };

    const handleCloseError = (
        <Button color="secondary" size="small" onClick={() => {
            setErrorMessage(false)
        }}>
            Close
        </Button>
    );

    return (
        !isAuthenticating && (
            <SessionContext.Provider value={{
                isAuthenticated,
                userHasAuthenticated,
                authenticatedUserName,
                setIsSidebarOpen,
                isSidebarOpen,
                errorMessage,
                setErrorMessage
            }}>
                <CssBaseline/>
                <DemoContainer bgType='light'>
                    <Grid container direction="column" style={{overflowY: "scroll"}}>
                        <Grid item>
                            {authenticatedUserName &&
                            <Header
                                customerLogoUrl={config.HEADER_LOGO}
                                onLogout={handleLogout}
                                loginName={authenticatedUserName}
                            />
                            }
                        </Grid>

                        <Grid container direction="row">
                            <Grid item className={clsx({
                                [classes.openSidebar]: isSidebarOpen,
                                [classes.closedSidebar]: !isSidebarOpen,
                            })}>
                                <Sidebar
                                    menu={[
                                        {
                                            text: 'Events', navigate: () => {
                                                props.history.push("/listEvents")
                                            }
                                        },
                                        {
                                            text: 'Replays', navigate: () => {
                                                props.history.push("/listReplays")
                                            }
                                        },
                                        {
                                            text: 'Profiles', navigate: () => {
                                                props.history.push("/listProfiles")
                                            }
                                        },
                                        {
                                            text: 'Plugins', navigate: () => {
                                                props.history.push("/listPlugins")
                                            }
                                        },
                                        {
                                            text: 'Models', navigate: () => {
                                                props.history.push("/listModels")
                                            }
                                        }
                                    ]}
                                    open={isSidebarOpen}
                                    handleDrawerOpen={handleDrawerOpen}
                                    handleDrawerClose={handleDrawerClose}
                                />
                            </Grid>
                            <Grid item sm={12}>
                                <Box py={8}
                                     className={clsx({
                                         height: "100vh",
                                         [classes.routesWithOpenSidebar]: isSidebarOpen,
                                         [classes.routesWithClosedSidebar]: !isSidebarOpen,
                                     })}>
                                    <Box py={2} className={classes.alert}>
                                        {errorMessage &&
                                        <SnackbarContent message={errorMessage} action={handleCloseError}/>}
                                    </Box>
                                    <Routes/>
                                </Box>
                            </Grid>
                        </Grid>
                        {authenticatedUserName &&
                        <Grid item>

                            <Footer/>
                        </Grid>
                        }
                    </Grid>
                </DemoContainer>
            </SessionContext.Provider>
        )
    )
};

export default withRouter(App);
