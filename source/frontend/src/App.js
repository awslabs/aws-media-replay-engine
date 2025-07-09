/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React, {useState, useEffect} from "react";
import {useNavigate} from "react-router-dom";
import {withRouter} from "./common/utils/withRouter"
import {fetchAuthSession, signOut} from "aws-amplify/auth";

import config from "./config";
import {SessionContext} from "./contexts/SessionContext";

import "./App.css";
import CssBaseline from '@material-ui/core/CssBaseline';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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
        width: 200,
    },
    closedSidebar: {
        width: 200,
    },
    routesWithOpenSidebar: {
        paddingLeft: 40,
        paddingRight: 40

    },
    routesWithClosedSidebar: {
        paddingLeft: 40,
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

const queryClient = new QueryClient();

const App = (props) => {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [authenticatedUserName, setAuthenticatedUserName] = useState('');
    const [isAuthenticating, setIsAuthenticating] = useState(true);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [errorMessage, setErrorMessage] = useState(undefined);

    const navigate = useNavigate();
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
            const session = (await fetchAuthSession()).tokens ?? {};
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
        //await signOut();
        // Perform global sign out
        await signOut({ global: true });
        
        // Clear any local storage
        localStorage.clear();
        sessionStorage.clear();
        userHasAuthenticated(false);
        navigate("/login");
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
            <QueryClientProvider client={queryClient}>
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
                            <Grid item sm={1} className={clsx({
                                [classes.openSidebar]: isSidebarOpen,
                                [classes.closedSidebar]: !isSidebarOpen,
                            })}>
                                <Sidebar
                                    menu={[
                                        {
                                            text: 'Events', navigate: () => {
                                                navigate("/listEvents")
                                            }
                                        },
                                        {
                                            text: 'Replays', navigate: () => {
                                                navigate("/listReplays")
                                            }
                                        },
                                        {
                                            text: 'Profiles', navigate: () => {
                                                navigate("/listProfiles")
                                            }
                                        },
                                        {
                                            text: 'Plugins', navigate: () => {
                                                navigate("/listPlugins")
                                            }
                                        },
                                        {
                                            text: 'Models', navigate: () => {
                                                navigate("/listModels")
                                            }
                                        },
                                        {
                                            text: 'Prompts', navigate: () => {
                                                navigate("/listPrompts")
                                            }
                                        }
                                    ]}
                                    open={isSidebarOpen}
                                    handleDrawerOpen={handleDrawerOpen}
                                    handleDrawerClose={handleDrawerClose}
                                />
                            </Grid>
                            <Grid item sm={11}>
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
            </QueryClientProvider>
        )
    )
};

export default withRouter(App);
