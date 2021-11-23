/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React, {useState} from "react";
import {Auth} from "aws-amplify";
import {useHistory, useLocation} from "react-router-dom";

import Avatar from '@material-ui/core/Avatar';
import Box from '@material-ui/core/Box';
import LockOutlinedIcon from '@material-ui/icons/LockOutlined';
import Typography from '@material-ui/core/Typography';
import {makeStyles} from '@material-ui/core/styles';
import Grid from '@material-ui/core/Grid';

import {Copyright} from '../../common/Copyright';
import {LoginForm} from "./LoginForm";
import {useSessionContext} from "../../contexts/SessionContext";

const useStyles = makeStyles((theme) => ({
    box: {
        marginTop: theme.spacing(8)
    },
    paper: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center'
    },
    avatar: {
        margin: theme.spacing(1),
        backgroundColor: theme.palette.secondary.main,
    },
}));

export const Login = (props) => {
    const [isLoading, setIsLoading] = useState(false);
    const classes = useStyles();
    const history = useHistory();
    const {state} = useLocation();

    const {userHasAuthenticated} = useSessionContext();

    const confirmNewPassword = async (signInResponse, password) => {
        console.log('This is the first time this user logs in. The user requires changing (or confirming) password');
        console.log('Auto-confirm user password');
        await Auth.completeNewPassword(
            signInResponse,
            password,
            signInResponse.challengeParam.requiredAttributes
        );
        console.log("Auth.completeNewPassword succeeded");
    };

    const handleSubmit = async (username, password) => {
        setIsLoading(true);
        try {
            const signInResponse = await Auth.signIn(username, password);
            if (signInResponse.challengeName === "NEW_PASSWORD_REQUIRED") {
                await confirmNewPassword(signInResponse, password);
            }
            userHasAuthenticated(signInResponse.username);

            history.push(state?.from || '/');
        } catch (e) {
            alert(e.message);
            setIsLoading(false);
        }
    };

    return (
        <Grid container
              spacing={0}
              direction="column"
              alignItems="center"
              style={{
                  minHeight: '100vh',
                  justifyContent: 'center'
              }}>
            <Grid className={classes.paper} item>
                <Avatar className={classes.avatar}>
                    <LockOutlinedIcon/>
                </Avatar>
                <Typography component="h1" variant="h5">
                    Sign in
                </Typography>
                <LoginForm
                    isLoading={isLoading}
                    onSubmit={handleSubmit}
                />
                <Box mt={8} className={classes.box}>
                    <Copyright/>
                </Box>
            </Grid>
        </Grid>
    );
}