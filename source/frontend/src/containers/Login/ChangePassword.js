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
    },

}));

export const ChangePasswordForm = (props) => {
    const [username, setUsername] = useState(props.username);
    const [password, setPassword] = useState("");
    const classes = useStyles();

    const validateForm = () => {
        return username.length > 0 && password.length > 0;
    };

    const handlePasswordChange = (e) => setPassword(e.target.value);

    const handleSubmit = event => {
        event.preventDefault();

        const {onSubmit} = props;
        onSubmit(password);
    };

    return (
        <form className={classes.form} onSubmit={handleSubmit}>
            <TextField
                variant="outlined"
                margin="normal"
                required
                fullWidth
                id="username"
                label="Username"
                name="username"
                disabled={true}
                value={username}
                //onChange={handleUserNameChange}
                //autoFocus
            />
            <TextField
                variant="outlined"
                margin="normal"
                required
                fullWidth
                name="password"
                label="New Password"
                type="password"
                id="password"
                autoComplete="current-password"
                value={password}
                onChange={handlePasswordChange}
                autoFocus/>
                
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
            {props.isLoading &&
            <Backdrop open={true} className={classes.backdrop}>
                <CircularProgress color="inherit"/>
            </Backdrop>
            }
        </form>
    );
};
