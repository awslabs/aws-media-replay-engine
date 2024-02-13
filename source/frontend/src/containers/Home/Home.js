/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {useNavigate} from "react-router-dom";
import Grid from "@material-ui/core/Grid";
import {Container, Paper} from "@material-ui/core";
import Box from "@material-ui/core/Box";
import Link from "@material-ui/core/Link";
import homeImage from "../../assets/home_image.svg"

export const Home = (props) => {
    const navigate = useNavigate();
    const navigateTo = route => navigate(route);
    const preventDefault = (event) => event.preventDefault();

    React.useEffect(() => {

    }, []);


    return (
        <Box pt={8}>
            <Grid container direction="column" justify="center" alignItems="center" spacing={5}>
                <Grid item>
                    <Container maxWidth="lg">
                        <img src={homeImage} style={{width: "45vw"}} alt={"home_image"}/>
                    </Container>
                </Grid>
                <Grid item>
                    <Link href="https://github.com/awslabs/aws-media-replay-engine/blob/main/MRE-Developer-Guide.md" target="_blank">
                        Learn more about how to use this solution
                    </Link>
                </Grid>
            </Grid>
        </Box>
    );
};