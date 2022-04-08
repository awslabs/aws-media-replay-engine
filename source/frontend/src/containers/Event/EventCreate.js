/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {FormRenderer} from "../../components/Form/FormRenderer";
import _ from "lodash";
import {ProgramCreateModal} from "../../components/Programs/ProgramCreateModal";
import {Backdrop, CircularProgress} from "@material-ui/core";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import {makeStyles} from "@material-ui/core/styles";
import {EXECUTION_TYPES, LAMBDA_WITH_VERSION_ARN_REGEX} from "../../common/Constants";

const useStyles = makeStyles((theme) => ({
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },

}));

export const EventCreate = () => {
    const classes = useStyles();

    const [programOptions, setProgramOptions] = React.useState([]);
    const [profileOptions, setProfileOptions] = React.useState([]);
    const [profilesData, setProfilesData] = React.useState([]);
    const [channelOptions, setChannelOptions] = React.useState([]);

    const {query, isLoading, setIsLoading} = APIHandler();


    const fetchChannels = async () => {
        let response = await query('get', 'api', 'system/medialive/channels', {disableLoader: true});
        return response.data;
    }

    const fetchProfile = async () => {
        let response = await query('get', 'api', 'profile/all', {disableLoader: true});
        return response.data;
    };

    const fetchPrograms = async () => {
        let response = await query('get', 'api', 'program/all',{disableLoader: true});
        return _.map(response.data, "Name");
    };


    React.useEffect(() => {
        (async () => {
            setIsLoading(true);
            try {
                const [programOptions, profileOptions, channelOptions] = await Promise.all([fetchPrograms(), fetchProfile(), fetchChannels()])

                setProgramOptions(programOptions);
                setProfilesData(profileOptions);
                setProfileOptions(_.map(profileOptions, "Name"));
                setChannelOptions(channelOptions);
            }
            finally {
                setIsLoading(false);
            }
        })();
    }, []);


    const onProgramAdd = async () => {
        let updatedContentGroups = await fetchPrograms();
        setProgramOptions(updatedContentGroups);
    }

    const isJsonString = (str) => {
        try {
            return (JSON.parse(str) && !!str);
        } catch (e) {
            return false;
        }
    }

    const initialFormValues = {
        Program: "",
        Name: "",
        Description: "",
        Channel: "",
        Start: new Date(),
        DurationMinutes: '',
        Profile: "",
        ContentGroup: "",
        Archive: false,
        SourceVideoUrl: "",
        SourceVideoAuth: "",
        SourceVideoMetadata: "",
        BootstrapTimeInMinutes: 0
    };

    const inputFieldsMap = {
        Program: {
            name: "Program",
            label: "Program",
            type: "select",
            isRequired: true,
            options: programOptions,
            ItemComponent: <ProgramCreateModal onSuccessFunction={onProgramAdd}/>
        },
        Name: {
            name: "Name",
            label: "Event Name",
            type: "textField",
            isRequired: true
        },
        Description: {
            name: "Description",
            label: "Description",
            multiline: true,
            rows: 3,
            type: "textField",
            isRequired: false
        },
        MediaLive: {
            name: "MediaLive",
            label: "Use Media Live",
            type: "checkbox",
        },
        Channel: {
            name: "Channel",
            label: "Channel",
            type: "select",
            options: channelOptions,
            isRequired: (values) => {return values.MediaLive === true},
            displayName: (channelOption) => {
                return `${channelOption.Name} - ${channelOption.Id}`;
            },
            condition: (values) => {
                return values.MediaLive && values.MediaLive === true;
            },
        },
        ProgramId: {
            name: "ProgramId",
            label: "Program ID",
            type: "textField",
            condition: (values) => {
                return values.MediaLive !== true;
            },
        },
        SourceVideoUrl: {
            name: "SourceVideoUrl",
            label: "Source Video URL",
            type: "textField",
            isRequired: (values) => {return values.MediaLive !== true},
            condition: (values) => {
                return values.MediaLive !== true;
            },
        },
        SourceVideoAuth: {
            name: "SourceVideoAuth",
            label: "Source Video Auth (JSON)",
            type: "textField",
            condition: (values) => {
                return values.MediaLive !== true;
            },
            multiline: true,
            rows: 3,
            specialValidationFunction: (value) => {
                let isValidValue = isJsonString(value);
                return isValidValue ? "" : "Value should be JSON structure"
            }
        },
        SourceVideoMetadata: {
            name: "SourceVideoMetadata",
            label: "Source Video Metadata (JSON)",
            type: "textField",
            multiline: true,
            rows: 3,
            condition: (values) => {
                return values.MediaLive !== true;
            },
            specialValidationFunction: (value) => {
                let isValidValue = isJsonString(value);
                return isValidValue ? "" : "Value should be JSON structure"
            }
        },
        BootstrapTimeInMinutes: {
            name: "BootstrapTimeInMinutes",
            label: "Bootstrap Time (minutes)",
            type: "textField",
            textFieldType: "number",
            size: 3,
            condition: (values) => {
                return values.MediaLive !== true;
            },
        },
        Start: {
            name: "Start",
            label: "Start",
            type: "timePicker",
            isRequired: true
        },
        DurationMinutes: {
            name: "DurationMinutes",
            label: "Duration (Minutes)",
            type: "textField",
            textFieldType: "number",
            isRequired: true,
            size: 3
        },
        Profile: {
            name: "Profile",
            label: "Profile",
            type: "select",
            isRequired: true,
            options: profileOptions,
        },
        ContentGroup: {
            name: "ContentGroup",
            label: "Content Group",
            type: "select",
            isRequired: true,
            isDisabled: (values) => {
                return _.isEmpty(values.Profile);
            },
            optionsFunc: (values) => {
                if (values.Profile) {
                    return _.find(profilesData, {"Name": values.Profile})["ContentGroups"];
                }
            },
        },
        Archive: {
            name: "Archive",
            label: "Archive the event",
            type: "checkbox",
        }
    }

    return (
        <div>
            {
                isLoading ?
                    <div>
                        <Backdrop open={true} className={classes.backdrop}>
                            <CircularProgress color="inherit"/>
                        </Backdrop>
                    </div> :
                    <FormRenderer
                        initialFormValues={initialFormValues}
                        inputFieldsMap={inputFieldsMap}
                        breadCrumb={"Events"}
                        header={"Create Event"}
                        name={"event"}
                        history={"/listEvents"}
                    />
            }
        </div>
    );
}

