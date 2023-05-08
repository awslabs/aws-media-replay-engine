/*
 *
 *  * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *  * SPDX-License-Identifier: MIT-0
 *
 */

import {React, useState, useEffect} from "react";
import {withRouter} from "react-router-dom";
import {Auth} from "aws-amplify";

import config from "./config";
import {SessionContext} from "./contexts/SessionContext";

import "./App.css";

import DemoContainer from './components/Layouts/DemoContainer';
import Header from "./components/Header/Header";
import {makeStyles} from "@material-ui/core/styles";

import Routes from "./Routes";

const useStyles = makeStyles((theme) => ({
}));

function App(props) {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [authenticatedUserName, setAuthenticatedUserName] = useState('');
    const [isAuthenticating, setIsAuthenticating] = useState(true);
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

    return (
        !isAuthenticating && (
            <SessionContext.Provider value={{isAuthenticated, userHasAuthenticated, authenticatedUserName}}>
                <DemoContainer bgType='light'>
                    {authenticatedUserName &&
                    //@todo menu to pull from routes script?
                    <Header
                        customerLogoUrl={config.HEADER_LOGO}
                        onLogout={handleLogout}
                        loginName={authenticatedUserName}
                    />}
                    <div>
                        <Routes/>
                    </div>
                </DemoContainer>
            </SessionContext.Provider>
        )
    );
}

export default withRouter(App);
