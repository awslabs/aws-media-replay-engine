/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {makeStyles} from '@material-ui/core/styles';
import {CircularProgress, Container, FormControl, FormLabel, MenuItem, Select} from "@material-ui/core";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import _ from "lodash";



const useStyles = makeStyles((theme) => ({
    field: {
        paddingBottom: 5
    }
}));

export const TransitionsDropdown = (props) => {
    const classes = useStyles();
    const [transitionsOptions, setTransitionsOptions] = React.useState('None');


    const {query, isLoading} = APIHandler();

    React.useEffect(() => {
        (async () => {
            let res = await query('get', 'api', 'replay/transitions/all');
            let transitions = res.data;
            
            let finalTransitions = _.orderBy(_.map(transitions, "Name"))
            finalTransitions.push('None')
            setTransitionsOptions(finalTransitions);
            
        })();
    }, []);


    const handleChange = async (event) => {
        if (event.target.value !== "None"){
            try {
                let res = await query('get', 'api', `replay/transition/${event.target.value}`);
                props.handleTransitionChange(event.target.value, res.data)
            }
            catch (error) {
                console.log(error);
            }
        }
        else{
            props.handleTransitionChange(event.target.value, {})
        }
        
    }

    return (
        <FormControl variant="outlined" size="small"  style={{width: "400px", paddingLeft: "40px"}} >
            {
                !props.DisableLabel &&
                <FormLabel className={classes.field}>Transition</FormLabel>
            }
            {
                isLoading ?
                    <Container>
                        <CircularProgress color="inherit"/>
                    </Container> :
                    <>
                    <Select
                        value={props.selected}
                        //onChange={props.handleChange}
                        onChange={handleChange}
                    >
                        {props.hasSelectAll !== false && <MenuItem value={"ALL"}>Select All</MenuItem>}
                        {
                            _.map(transitionsOptions, (transition, index) => {
                                return (
                                    <MenuItem key={index} value={transition}>{transition}</MenuItem>
                                )
                            })
                        }
                    </Select>
                    
                    </>
            }

        </FormControl> 
    );
};