/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import _ from "lodash";


export const parseReplayDetails = (replayDetails, row) => {
    let parsedReplayDetails = {};
    parsedReplayDetails["Name"] = row.Program + ":" + row.Event;
    parsedReplayDetails["Program"] = row.Program;
    parsedReplayDetails["Event"] = row.Event;
    parsedReplayDetails["AudioTrack"] = _.get(replayDetails, "AudioTrack");
    parsedReplayDetails["Duration"] = _.get(replayDetails, "DurationbasedSummarization.Duration");
    parsedReplayDetails["DurationTolerance"] = _.get(replayDetails, "DurationbasedSummarization.ToleranceMaxLimitInSecs");
    parsedReplayDetails["EqualDistribution"] = _.get(replayDetails, "DurationbasedSummarization.EqualDistribution") ? "Yes" : "No"; 
    parsedReplayDetails["Description"] = _.get(replayDetails, "Description");
    parsedReplayDetails["Requester"] = _.get(replayDetails, "Requester");
    parsedReplayDetails["Catchup"] = _.get(replayDetails, "Catchup") ? "Yes" : "No";
    parsedReplayDetails["CreateHls"] = _.get(replayDetails, "CreateHls") ? "Yes" : "No";
    parsedReplayDetails["CreateMp4"] = _.get(replayDetails, "CreateMp4") ? "Yes" : "No";
    parsedReplayDetails["OutputResolutions"] = _.get(replayDetails, "Resolutions");
    parsedReplayDetails["TransitionName"] = _.get(replayDetails, "TransitionName");
    parsedReplayDetails["IgnoreDislikedSegments"] = _.get(replayDetails, "IgnoreDislikedSegments") ? "Yes" : "No";
    parsedReplayDetails["IncludeLikedSegments"] = _.get(replayDetails, "IncludeLikedSegments") ? "Yes" : "No";
    parsedReplayDetails["TransitionOverride"] = _.get(replayDetails, "TransitionOverride");
    parsedReplayDetails["MediaTailorProgram"] = _.has(replayDetails, "MediaTailorChannel") ? "Yes" : "No";
    parsedReplayDetails["MediaTailorChannel"] = _.get(replayDetails, 'MediaTailorChannel.ChannelName') || "N/A";
    parsedReplayDetails["UxLabel"] = _.get(replayDetails, 'UxLabel') || "N/A";
    parsedReplayDetails["MediaTailorAD"] = _.has(replayDetails, 'MediaTailorChannel.AdInsertionConfig') || "N/A";
    parsedReplayDetails["InsertAdds"] = _.has(replayDetails, 'MediaTailorChannel.ScheduleDimensionInMins') ? `${replayDetails.MediaTailorChannel.ScheduleDimensionInMins} Minutes` : "N/A";
    parsedReplayDetails["PriorityList"] = {Priorities: replayDetails.Priorities, replayDetails: replayDetails.ClipfeaturebasedSummarization}

    return parsedReplayDetails;
}