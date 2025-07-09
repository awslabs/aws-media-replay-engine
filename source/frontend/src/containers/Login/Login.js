/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React, {useState} from "react";
import {updatePassword, signIn, resetPassword, ResetPasswordOutput, confirmResetPassword, confirmSignIn} from "aws-amplify/auth"
import {useNavigate, useLocation} from "react-router-dom";

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
    const navigate = useNavigate();
    const {state} = useLocation();

    const [changePassword, setChangePassword] = useState(false);
    const [username, setUsername] = useState("");
    const [signInResponse, setSignInResponse] = useState(undefined);

    const {userHasAuthenticated} = useSessionContext();

    // Resets the user password in Cog Pool - for when user has first signed in
    const confirmNewPassword = async (newPassword) => {
        setIsLoading(true);
        
        try{
            const confirmedResponse = await confirmSignIn({challengeResponse: newPassword});
            console.log(confirmedResponse.username)
            userHasAuthenticated(username);
            setSignInResponse(confirmedResponse)
            navigate(state?.from || '/');
        }
        catch (e) {
            alert(e.message);
            setIsLoading(false);
        }
    };

    // Signs in the user, or prompts them to change their password if that is required on first sign in
    const handleSubmit = async (username, password) => {
        setIsLoading(true);
        try {
            setUsername(username)
            const signInResponse = await signIn({username, password});
            console.log(signInResponse)
            if (signInResponse.nextStep.signInStep === "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED") {
                setIsLoading(false);
                setChangePassword(true)
                setSignInResponse(signInResponse)
            }
            else{
                userHasAuthenticated(username);
                navigate(state?.from || '/');
            }
            
        } catch (e) {
            if (e.name === "UserNotFoundException") {
                alert("Incorrect username or password. Please try again.");
            }
            setIsLoading(false);
        }
    };

    // Changes User Password in Cog Pool - for when user has forgotten it
    const handleForgotPassword = async(username, onEmailed) => {
      try {
        const output = await resetPassword({ username });
        const { nextStep } = output;
        
        switch (nextStep.resetPasswordStep) {
            case 'CONFIRM_RESET_PASSWORD_WITH_CODE':
              const codeDeliveryDetails = nextStep.codeDeliveryDetails;
              console.log(
                `Confirmation code was sent to ${codeDeliveryDetails.deliveryMedium}`
              );
              console.log(output)
              onEmailed(true)
              break;
            case 'DONE':
              console.log('Successfully reset password.');
              break;
        }
        
      } catch (e) {
        alert(e.message);
        console.log(e);
    
      }
    }
    
    const handleConfirmResetPassword = async (username, newPassword, confirmationCode) => {
      try{
        const res = await confirmResetPassword({username, newPassword, confirmationCode})    
        console.log(res)
      } catch(e) {
        alert(e.message);
        console.log(e)
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
                            onForgotPassword={handleForgotPassword}
                            onPasswordChangeSubmit={handleConfirmResetPassword}
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