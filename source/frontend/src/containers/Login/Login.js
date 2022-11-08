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
import {ChangePasswordForm} from "./ChangePassword";
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
        
    },
    
}));

export const Login = (props) => {
    const [isLoading, setIsLoading] = useState(false);
    const classes = useStyles();
    const history = useHistory();
    const {state} = useLocation();

    const [changePassword, setChangePassword] = useState(false);
    const [username, setUsername] = useState("");
    const [signInResponse, setSignInResponse] = useState(undefined);

    const {userHasAuthenticated} = useSessionContext();

    const confirmNewPassword = async (password) => {
        setIsLoading(true);
        
        try{
        await Auth.completeNewPassword(
            signInResponse,
            password,
            signInResponse.challengeParam.requiredAttributes
        );
        userHasAuthenticated(signInResponse.username);
        history.push(state?.from || '/');
        
        }
        catch (e) {
            alert(e.message);
            setIsLoading(false);
        }
    };

    const handleSubmit = async (username, password) => {
        setIsLoading(true);
        try {
            setUsername(username)
            const signInResponse = await Auth.signIn(username, password);
            if (signInResponse.challengeName === "NEW_PASSWORD_REQUIRED") {
                setIsLoading(false);
                setChangePassword(true)
                setSignInResponse(signInResponse)
            }
            else{
                userHasAuthenticated(signInResponse.username);
                history.push(state?.from || '/');
            }
            
        } catch (e) {
            alert(e.message);
            setIsLoading(false);
        }
    };

    // Changes User Password in Cog Pool
    const passwordChangeSubmit = async (username, code, password) => {
        setIsLoading(true);
        try {
            await Auth.forgotPasswordSubmit(username, code, password)
            setIsLoading(false);

            setChangePassword(false)
            setUsername("")
            setSignInResponse(undefined)
            history.push('/');
        } catch (e) {
            
            setIsLoading(false);
            alert(e.message);
        }
        
    };

    // Sends an Email to the User EmailId
    const forgotPassword = async (username, onEmailed) => {
        try{
            if (username.trim() === ""){
                alert("Username cannot be empty !")
                return
            }
            // Send confirmation code to user's email
            const res = await Auth.forgotPassword(username)
            console.log(res);
            onEmailed(true)
            console.log('Emailed');
        }
        catch (e) {
            onEmailed(false)

            if (e.code === 'NotAuthorizedException') {
                alert("Incorrect password or you haven't signed into MRE at least once in the past");
            }
            else if (e.code === "UserNotFoundException") {
                alert("Username not found");
            }
            else
                alert(e.message);

            setIsLoading(false);
        }
    }

    return (
        <Grid container
              spacing={0}
              direction="column"
              alignItems="center"
              style={{
                  minHeight: '75vh',
                  justifyContent: 'center'
              }}>
                {
                    changePassword ? (
                        <Grid className={classes.paper} item>
                            <Avatar className={classes.avatar}>
                                <LockOutlinedIcon color="primary"/>
                            </Avatar>
                            <Typography component="h1" variant="h5">
                                Update your password
                            </Typography>
                            <Typography component="h1" variant="caption">
                                You need to update your password because this is the first time you are signing in.
                            </Typography>
                            <ChangePasswordForm
                                isLoading={isLoading}
                                onSubmit={confirmNewPassword}
                                username={username}
                            />
                            <Box mt={8} className={classes.box}>
                                <Copyright/>
                            </Box>
                        </Grid>
                    ) :
                    (
                        <Grid className={classes.paper} item>
                        <Avatar className={classes.avatar}>
                            <LockOutlinedIcon color="primary"/>
                        </Avatar>
                        
                        
                        <LoginForm
                            isLoading={isLoading}
                            onSubmit={handleSubmit}
                            onForgotPassword={forgotPassword}
                            onPasswordChangeSubmit={passwordChangeSubmit}
                        />
                        <Box mt={8} className={classes.box}>
                            <Copyright/>
                        </Box>
                    </Grid>
                    )
                }
            
        </Grid>
    );
}