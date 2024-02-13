/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React, {useState} from "react";

import Button from '@material-ui/core/Button';
import TextField from '@material-ui/core/TextField';
import Backdrop from '@material-ui/core/Backdrop';
import CircularProgress from '@material-ui/core/CircularProgress';
import {makeStyles} from '@material-ui/core/styles';
import { Link } from 'react-router-dom';
import Typography from '@material-ui/core/Typography';

const useStyles = makeStyles((theme) => ({
    form: {
        width: '100%', // Fix IE 11 issue.
        marginTop: theme.spacing(1),
    },
    submit: {
        margin: theme.spacing(3, 0, 2),
    },
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    }
    
}));

export const LoginForm = (props) => {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    const [emailCode, setEmailCode] = useState("");
    const [repeatPassword, setRepeatPassword] = useState("");

    const [forgotPassword, setForgotPassword] = useState(false);

    const classes = useStyles();

    const validateForm = () => {
        return username.length > 0 && password.length > 0;
    };

    const validatePasswordChangeForm = () => {
        return (
          username.length > 0 &&
          password.trim().length > 0 &&
          emailCode.trim().length > 0 &&
          repeatPassword.trim().length > 0 && 
          password.trim() === repeatPassword.trim()
        );
    };

    const handleUserNameChange = (e) => setUsername(e.target.value);
    const handlePasswordChange = (e) => setPassword(e.target.value);
    const handleCodeChange = (e) => setEmailCode(e.target.value);
    const handleRepeatPasswordChange = (e) => setRepeatPassword(e.target.value);
    

    const handleSubmit = event => {
        event.preventDefault();

        if (!forgotPassword){
            const {onSubmit} = props;
            onSubmit(username, password);
        }
        else{
            const {onPasswordChangeSubmit} = props;
            onPasswordChangeSubmit(username, password, emailCode);
        }
    };

    const handleForgotPassword = event => {
        event.preventDefault();

        const {onForgotPassword} = props;
        // Send email to User with Code
        onForgotPassword(username, onEmailed);
        
    }

    const onEmailed = emailed => {
        setForgotPassword(emailed)
    }

    return (
        <form className={classes.form} onSubmit={handleSubmit} style={{textAlign: 'center'}}>
            {
                !forgotPassword ? (
                    <>
                        <Typography component="h1" variant="h5">
                            Sign in
                        </Typography>
                        <TextField
                            variant="outlined"
                            margin="normal"
                            required
                            fullWidth
                            id="username"
                            label="Username"
                            name="username"
                            autoComplete="username"
                            value={username}
                            onChange={handleUserNameChange}
                            autoFocus
                        />
                        <TextField
                            variant="outlined"
                            margin="normal"
                            required
                            fullWidth
                            name="password"
                            label="Password"
                            type="password"
                            id="password"
                            autoComplete="current-password"
                            value={password}
                            onChange={handlePasswordChange}/>
                        
                        <Link style={{color: '#fb5e03', textDecoration: 'none', float: 'left'}} to={''} onClick={handleForgotPassword}>
                            Forgot your password ?
                        </Link>
                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            color="primary"
                            className={classes.submit}
                            disabled={!validateForm()}
                        >
                            Sign In
                        </Button>
                    </>
                ) :
                (
                    <>
                        <Typography component="h1" variant="h5">
                            Change Password
                        </Typography>
                        <Typography component="h1" variant="subtitle1">
                            We have sent a password reset code by email. Enter it below to reset your password.
                        </Typography>
                        <TextField
                            variant="outlined"
                            margin="normal"
                            required
                            fullWidth
                            id="code"
                            label="Code"
                            name="code"
                            autoComplete="code"
                            value={emailCode}
                            onChange={handleCodeChange}
                            autoFocus
                        />
                        <TextField
                            variant="outlined"
                            margin="normal"
                            required
                            fullWidth
                            name="newpassword"
                            label="New Password"
                            type="password"
                            id="newpassword"
                            autoComplete="newpassword"
                            value={password}
                            onChange={handlePasswordChange}/>
                        <TextField
                            variant="outlined"
                            margin="normal"
                            required
                            fullWidth
                            name="newpasswordagain"
                            label="Enter New Password Again"
                            type="password"
                            id="newpasswordagain"
                            autoComplete="newpasswordagain"
                            value={repeatPassword}
                            onChange={handleRepeatPasswordChange}/>
                        <Button
                            type="submit"
                            fullWidth
                            variant="contained"
                            color="primary"
                            className={classes.submit}
                            disabled={!validatePasswordChangeForm()}
                        >
                            Change Password
                        </Button>
                    </>
                )
            }
            {props.isLoading &&
            <Backdrop open={true} className={classes.backdrop}>
                <CircularProgress color="inherit"/>
            </Backdrop>
            }
        </form>
    );
};
