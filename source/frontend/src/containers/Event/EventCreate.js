/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {FormRenderer} from "../../components/Form/FormRenderer";
import _ from "lodash";
import {ProgramCreateModal} from "../../components/Programs/ProgramCreateModal";
import {Backdrop, CircularProgress, Tooltip} from "@material-ui/core";
import {APIHandler} from "../../common/APIHandler/APIHandler";
import {makeStyles} from "@material-ui/core/styles";
import {EXECUTION_TYPES, LAMBDA_WITH_VERSION_ARN_REGEX} from "../../common/Constants";
import moment from "moment";

const useStyles = makeStyles((theme) => ({
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },

}));

export const EventCreate = () => {
    const classes = useStyles();

    const sourceTypes = {
        UNDEFINED: '',
        MEDIALIVE:'MediaLive',
        HARVESTER:'HLS Harvester',
        S3_BUCKET:'S3 Bucket'
    };

    const timeCodes = {
        UNDEFINED: '',
        NONE:'NOT_EMBEDDED',
        UTC:'UTC_BASED',
        ZERO_BASED:'ZERO_BASED'
    };

    const [programOptions, setProgramOptions] = React.useState([]);
    const [profileOptions, setProfileOptions] = React.useState([]);
    const [profilesData, setProfilesData] = React.useState([]);
    const [channelOptions, setChannelOptions] = React.useState([]);
    const [bucketOptions, setBucketOptions] = React.useState([]);
    const [timeCodeOptions, setTimeCodeOptions] = React.useState(Object.values(timeCodes));
    const [sourceOptions, setSourceOptions] = React.useState(Object.values(sourceTypes));
    const [eventMetadata, setEventMetadata] = React.useState([]);

    const {query, isLoading, setIsLoading} = APIHandler();


    const fetchChannels = async () => {
        let response = await query('get', 'api', 'system/medialive/channels', {disableLoader: true});
        return response.data;
    }

    const fetchBuckets = async () => {
        let response = await query('get_cache', 'api', 'system/s3/buckets', {disableLoader: true}, {ttl: 30000}); // Cache for 30 seconds
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

    const fetchProfileMetadata = async (profile) => {
        let response = await query('get', 'api', `profile/${profile}/context-variables`, {disableLoader: true}, {ttl: 30000});
        return response.data?.data;
    }


    React.useEffect(() => {
        (async () => {
            setIsLoading(true);
            try {
                const [programOptions, profileOptions] = await Promise.all([fetchPrograms(), fetchProfile()])

                setProgramOptions(programOptions);
                setProfilesData(profileOptions);
                setProfileOptions(_.map(profileOptions, "Name"));
            }
            finally {
                setIsLoading(false);
            }
        })();
    }, []);

    const onTimeCodeChange= async (value) => {
        console.log(value)
    }

    const onSourceChange = async (value) => {
        if (value == sourceTypes.MEDIALIVE) {
            const channelOptions = await fetchChannels();
            setChannelOptions(channelOptions);
        }
        else if (value == sourceTypes.S3_BUCKET) {
            const bucketOptions = await fetchBuckets();
            setBucketOptions(bucketOptions);
        }
    }

    const onProgramAdd = async () => {
        let updatedContentGroups = await fetchPrograms();
        setProgramOptions(updatedContentGroups);
    }

    const onProfileChange = async (profile) => {
        let profileMetadata = await fetchProfileMetadata(profile);
        setEventMetadata(profileMetadata);
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
        BootstrapTimeInMinutes: 2,
        SourceSelection: sourceTypes.UNDEFINED,
        SourceVideoBucket: sourceTypes.UNDEFINED,
        GenerateOrigClips: true,
        GenerateOptoClips: true,
        TimecodeSource: timeCodes.NONE,
        StopMediaLiveChannel: false
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
        Profile: {
            name: "Profile",
            label: "Profile",
            type: "select",
            isRequired: true,
            options: profileOptions,
            onChange: (e) => {
                onProfileChange(e?.target?.value);
            }
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
        TimecodeSource: {
            name: "TimecodeSource",
            label: "Embedded Timecode Source",
            type: "select",
            isRequired: true,
            options: timeCodeOptions
        },
        SourceSelect: {
            name: "SourceSelection",
            label: "Video Chunk Source",
            type: "select",
            isRequired: true,
            options: sourceOptions,
            onChangeType: "selection",
            onChange: (e) => {
                onSourceChange(e?.target?.value);
            }
        },
        Channel: {
            name: "Channel",
            label: "Channel",
            type: "select",
            options: channelOptions,
            isRequired: (values) => {return values.SourceSelection && values.SourceSelection === sourceTypes.MEDIALIVE},
            displayName: (channelOption) => {
                return `${channelOption.Name} - ${channelOption.Id}`;
            },
            condition: (values) => {
                return values.SourceSelection && values.SourceSelection === sourceTypes.MEDIALIVE;
            },
        },
        StopMediaLiveChannel: {
            name: "StopMediaLiveChannel",
            label: "Stop channel when event ends ?",
            type: "checkbox",
            condition: (values) => {
                return values.SourceSelection && values.SourceSelection === sourceTypes.MEDIALIVE;
            },
            displayHelp: true,
            helpText: "When selected, MRE will stop the MediaLive channel after an event has ended."
        },
        ProgramId: {
            name: "ProgramId",
            label: "Program ID",
            type: "textField",
            condition: (values) => {
                return values.SourceSelection === sourceTypes.HARVESTER;
            },
        },
        SourceVideoUrl: {
            name: "SourceVideoUrl",
            label: "Source Video URL",
            type: "textField",
            isRequired: (values) => {return values.SourceSelection === sourceTypes.HARVESTER},
            condition: (values) => {
                return values.SourceSelection === sourceTypes.HARVESTER;
            },
        },
        SourceVideoAuth: {
            name: "SourceVideoAuth",
            label: "Source Video Auth (JSON)",
            type: "textField",
            condition: (values) => {
                return values.SourceSelection === sourceTypes.HARVESTER;
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
                return values.SourceSelection === sourceTypes.HARVESTER;
            },
            specialValidationFunction: (value) => {
                let isValidValue = isJsonString(value);
                return isValidValue ? "" : "Value should be JSON structure"
            }
        },
        
        SourceVideoBucket: {
            name: "SourceVideoBucket",
            label: "Source S3 Bucket",
            type: "select",
            options: bucketOptions,
            isRequired: (values) => {return values.SourceSelection && values.SourceSelection === sourceTypes.S3_BUCKET},
            condition: (values) => {
                return values.SourceSelection && values.SourceSelection === sourceTypes.S3_BUCKET;
            }
        },
        S3BucketHint: {
            type: "formComponent",
            condition: (values) => {
                return values.SourceSelection && values.SourceSelection === sourceTypes.S3_BUCKET 
                && values.Program
                && values.Name
                && values.Profile
                && values.SourceVideoBucket
            },
            NestedFormRenderer: "ClickableInfoChip",
            parameters: {
                label: (values) => {
                    return  `Source video chunks should be uploaded to s3://${values.SourceVideoBucket}/${values.Program}/${values.Name}/${values.Profile}/ to process the event.`;
                },
                link: (values)=>{
                    return `https://s3.console.aws.amazon.com/s3/buckets/${values.SourceVideoBucket}?prefix=${values.Program}/${values.Name}/${values.Profile}/`
                },
                variant: "outlined"
            },
        },
        Start: {
            name: "Start",
            label: `Start (${moment().format('UTCZ')})`,
            type: "timePicker",
            isRequired: true,

        },
        DurationMinutes: {
            name: "DurationMinutes",
            label: "Duration (Minutes)",
            type: "textField",
            textFieldType: "number",
            isRequired: true,
            size: 3
        },
        BootstrapTimeInMinutes: {
            name: "BootstrapTimeInMinutes",
            label: "Bootstrap Time (minutes)",
            type: "textField",
            textFieldType: "number",
            size: 3,
            isRequired: true,
            condition: (values) => {
                return true; //values.SourceSelection === sourceTypes.HARVESTER;
            },
            displayHelp: true,
            helpText: "Time taken by MediaLive to start a channel and enter the RUNNING state or time taken by an external process to begin ingesting source video."
        },
        Archive: {
            name: "Archive",
            label: "Archive the event",
            type: "checkbox",
        },
        GenOriginalClip: {
            name: "GenerateOrigClips",
            label: "Generate Original Segment Clips",
            type: "checkbox",
        },
        GenOptimizedClip: {
            name: "GenerateOptoClips",
            label: "Generate Optimized Segment Clips",
            type: "checkbox",
        },
        Variables: {
            name: "Variables",
            label: "Context Variables",
            type: "keyValuePairs",
            keyValues:eventMetadata,
            defaultLocked: true,
            addButtonLabel: "Variable"
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

