/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {useHistory} from "react-router-dom";
import {makeStyles} from '@material-ui/core/styles';
import _ from "lodash";
import Box from "@material-ui/core/Box";
import Grid from "@material-ui/core/Grid";
import {
    Breadcrumbs,
    Typography,
    MenuItem, Select, FormLabel, CircularProgress, Backdrop, Tooltip, FormControl

} from "@material-ui/core";
import Link from "@material-ui/core/Link";
import IconButton from "@material-ui/core/IconButton";
import GridList from '@material-ui/core/GridList';
import {ThumbnailCard} from "../../components/Event/ThumbnailCard"
import {v1 as uuidv1} from 'uuid';
import {useSessionContext} from "../../contexts/SessionContext";
import randomColor from 'randomcolor';
import {ClipPreviewModal} from "../../components/ClipPreviewFeedback/ClipPreviewModal";
import {MultiSelectWithChips} from "../../components/MultiSelectWithChips/MultiSelectWithChips";
import {ClipPlayer} from "../../components/ClipPreviewFeedback/ClipPlayer"
import {ClipPlaceholder} from "../../components/ClipPreviewFeedback/ClipPlaceholder"
import {RangeBarChart} from "../../components/ClipPreviewFeedback/RangeBarChart"
import {RangeTable} from "../../components/ClipPreviewFeedback/RangeTable"
import {FeatureBarChart} from "../../components/ClipPreviewFeedback/FeatureBarChart"
import {APIHandler} from "../../common/APIHandler/APIHandler";
import AutorenewIcon from "@material-ui/icons/Autorenew";
import MoreHorizIcon from '@material-ui/icons/MoreHoriz';
import {ReplayViewDialog} from "../../components/Replay/ReplayViewDialog"
import {parseReplayDetails} from "../../components/Replay/common";
import {AWS_COLOR_PALETTE} from "../../components/ClipPreviewFeedback/RangeColorPallete"
import ArrowBackIosIcon from '@material-ui/icons/ArrowBackIos';
import ArrowForwardIosIcon from '@material-ui/icons/ArrowForwardIos';
import PlayCircleFilledIcon from "@material-ui/icons/PlayCircleFilled";
import {Dialog, DialogContent, DialogTitle, DialogActions} from "@material-ui/core";
import ReactPlayer from "react-player";
import Button from "@material-ui/core/Button";
import config from "../../config";

const useStyles = makeStyles((theme) => ({
    content: {
        marginTop: 'auto'
    },
    cardContainer: {
        padding: 0
    },
    gridList: {
        flexWrap: 'nowrap',
        // Promote the list into his own layer on Chrome. This cost memory but helps keeping high FPS.
        transform: 'translateZ(0)',
        overflowX: "scroll",
        overflowY: "hidden"
    },
    iconSize: {
        fontSize: "26px",
        marginBottom: 3,
        color: "white"
    },
    backdrop: {
        zIndex: theme.zIndex.drawer + 1,
        color: '#fff',
    },
}));

export const ClipPreview = () => {
        const classes = useStyles();
        const history = useHistory();
        const [selectedCard, setSelectedCard] = React.useState({})
        const [originalEventData, setOriginalEventData] = React.useState({})
        const stateParams = _.get(history, 'location.state');
        const [allClips, setAllClips] = React.useState(undefined);
        const {setIsSidebarOpen, isSidebarOpen, authenticatedUserName} = useSessionContext()
        
        const [rangeEvents, setOptimizedRangeEvents] = React.useState([])
        const [rangeEventsCharts, setOptimizedRangeEventsCharts] = React.useState([])
        const [clipFeatures, setOptimizedClipFeatures] = React.useState([])
        const [clipFeatureLabels, setOptimizedClipFeatureLabels] = React.useState([])
        const [pluginLabels, setOptimizedPluginLabels] = React.useState([])
        const [optimizedClipLocation, setOptimizedClipLocation] = React.useState('')

        const [originalRangeEvents, setOriginalRangeEvents] = React.useState([])
        const [originalRangeEventsCharts, setOriginalRangeEventsCharts] = React.useState([])
        const [originalClipFeatures, setOriginalClipFeatures] = React.useState([])
        const [originalClipFeatureLabels, setOriginalClipFeatureLabels] = React.useState([])
        const [originalPluginLabels, setOriginalPluginLabels] = React.useState([])
        const [originalClipLocation, setOriginalClipLocation] = React.useState('')

        const [selectedAudioTrack, setSelectedAudioTrack] = React.useState(1)
        const [sidebarOpen, setSidebarOpen] = React.useState(false)

        const [featureLabelColors, setFeatureLabelColors] = React.useState({})
        const [rangeEventColors, setRangeEventColors] = React.useState({})

        const [originalThumbsUp, setOriginalThumbsUp] = React.useState(false)
        const [optimizedThumbsUp, setOptimizedThumbsUp] = React.useState(false)
        const [clipPreviewOpen, setClipPreviewOpen] = React.useState(false);
        const [currentFeedbackMode, setCurrentFeedbackMode] = React.useState('');
        const [originalThumbsUpColor, setOriginalThumbsUpColor] = React.useState('');
        const [optimizedThumbsUpColor, setOptimizedThumbsUpColor] = React.useState('');
        const [originalThumbsDownColor, setOriginalThumbsDownColor] = React.useState('');
        const [optimizedThumbsDownColor, setOptimizedThumbsDownColor] = React.useState('');

        const [profileClassifier, setProfileClassifier] = React.useState('');

        const [optimizedFeedbackDetail, setOptimizedFeedbackDetail] = React.useState('')
        const [originalFeedbackDetail, setOriginalFeedbackDetail] = React.useState('')

        const [filterValues, setFilterValues] = React.useState([]);
        const [originalClipFeaturesRoot, setOriginalClipFeaturesRoot] = React.useState([])
        const [optimizedClipFeaturesRoot, setOptimizedClipFeaturesRoot] = React.useState([])

        const [allPluginNameColor, setAllPluginNameColor] = React.useState([])

        const [originalClipFeaturesTicks, setOriginalClipFeaturesTicks] = React.useState([])
        const [optimizedClipFeaturesTicks, setOptimizedClipFeaturesTicks] = React.useState([])

        const [clipPreviewMode, setClipPreviewMode] = React.useState('')
        const [completeReplayRequest, setCompleteReplayRequest] = React.useState(undefined)
        const [replayViewDialogOpen, setReplayViewDialogOpen] = React.useState(false)
        const [nextReplaysToken, setNextReplaysToken] = React.useState(undefined);
        const [currentClipPage, setCurrentClipPage] = React.useState(undefined);
        const [totalClipPages, setTotalClipPages] = React.useState(undefined);
        const [isClipsLoading, setIsClipsLoading] = React.useState(undefined);
        const [displayedClipList, setDisplayedClipList] = React.useState(undefined);
        const gridListRef = React.useRef();
        const [isOptimizerConfiguredInProfile, setIsOptimizerConfiguredInProfile] = React.useState(false);

        const {query, isLoading, setIsLoading} = APIHandler();
        const [checkBoxState, setCheckBoxState] = React.useState({
            checkedDislikeReset: false
        });
        const [originalDislikeResetCheckBoxState, setOriginalDislikeResetCheckBoxState] = React.useState(false)
        const [optoDislikeResetCheckBoxState, setoptoDislikeResetCheckBoxState] = React.useState(false)
        const [originalThumbsDown, setOriginalThumbsDown] = React.useState(false)
        const [optimizedThumbsDown, setOptimizedThumbsDown] = React.useState(false)
        const [originalAction, setOriginalAction] = React.useState(false)
        const [optimizedAction, setOptimizedAction] = React.useState(false)
        const [thumbsUpOrigLoading, setThumbsUpOrigLoading] = React.useState(false)
        const [thumbsUpOptoLoading, setThumbsUpOptoLoading] = React.useState(false)
        const [highlightClipOpen, setHighlightClipOpen] = React.useState(false)
        const [highlightClipVideoUrl, setHighlightClipVideoUrl]= React.useState('')
        const [loadingHighlightClipVideo, setLoadingHighlightClipVideo]= React.useState(false)

        const MAX_CLIPS = 10;

        React.useEffect(() => {
            setSidebarOpen(isSidebarOpen)
        }, [isSidebarOpen]);

        const handleDislikeResetCheckBoxChange = (event) => {
            setCheckBoxState({...checkBoxState, [event.target.name]: event.target.checked});

            ////console.log(`event.target.checked=${event.target.checked}`);
            ////console.log(currentFeedbackMode);
            if (event.target.checked && currentFeedbackMode === "Original"){
                setOriginalDislikeResetCheckBoxState(true)
            }
            else if (event.target.checked && currentFeedbackMode === "Optimized"){
                setoptoDislikeResetCheckBoxState(true)
            }
        };
        

        const getLatestEventState = async (origEventData) => {
            let latestEvent = await query('get', 'api', `event/${origEventData.Name}/program/${origEventData.Program}`, {disableLoader: true});
            return latestEvent.data;
        }

        const getPlugins = async () => {
            let response = await query('get', 'api', `plugin/all`, {disableLoader: true})
            const plugins = _.get(response, 'data')
            const pluginNamesWithColors = _.map(plugins, (plugin, index) => {
                return {
                    "PluginName": plugin.Name,
                    "Color": index >= AWS_COLOR_PALETTE.length ? AWS_COLOR_PALETTE[0].hex : AWS_COLOR_PALETTE[index].hex
                }
            })
            ////console.log(pluginNamesWithColors);
            setAllPluginNameColor(pluginNamesWithColors);
        }

        const goBack = () => {
            if (clipPreviewMode === "EventClips") {
                history.push({
                    pathname: "/viewEvent", state: {
                        back: {
                            name: "Events List",
                            link: "/viewEvent"
                        },
                        data: originalEventData,
                    }
                });
            }
            else {
                history.push({
                    pathname: "/listReplays", state: {
                        data: '',
                    }
                });
            }
        };

        if (!stateParams) {
            goBack();
        }

        

        React.useEffect(() => {
            (async () => {

                setClipPreviewMode(stateParams.mode)

                await getPlugins();

                // Force close the Left Navigation bar
                setIsSidebarOpen(false);

                if (stateParams.mode === "EventClips") {
                    await initializeViewClipPreview();
                }
                else {  //mode="ReplayClips"
                    await initializeReplayClipPreview();
                }

            })();

        }, []);

        const initializeViewClipPreview = async () => {
            const clipData = await _.get(stateParams, 'clipdata');
            const origEventData = await _.get(stateParams, 'origEventData')

            setIsLoading(true)

            let profileRes = await query('get', 'api', `profile/${origEventData.Profile}`, {disableLoader: true});
            profileRes = profileRes.data;

            setIsOptimizerConfiguredInProfile(_.get(profileRes, 'Optimizer.Name') !== undefined ? true : false)
            setProfileClassifier(profileRes.Classifier.Name);
            setSelectedCard(clipData);

            // Set the Latest Event State
            // This call is Required to get the AudioTracks which are not otherwise readily available
            // when an event is Created and the user quickly navigates to the Clip Preview Screen.
            // Step function takes a while to Extract and Persist AudioTracks at an Event level.
            setOriginalEventData(await getLatestEventState(origEventData))

            setTotalClipPages(_.ceil(_.size(_.get(stateParams, 'allClipsData')) / MAX_CLIPS));

            let allClipsData = _.chunk(_.get(stateParams, 'allClipsData'), MAX_CLIPS);
            
            _.forEach(allClipsData, page => {
                _.forEach(page, (allc) => {
                    allc.id = uuidv1()
                    allc.selected = clipData.OriginalThumbnailLocation === allc.OriginalThumbnailLocation;
                })
            })

            setAllClips(allClipsData)

            await Promise.all([getOptimizedRangeEvents(
                clipData, origEventData, profileRes.Classifier.Name),
                getOriginalRangeEvents(clipData, origEventData, profileRes.Classifier.Name),
                getClipReviewFeedback(clipData, origEventData, profileRes.Classifier.Name)
            ]);

            // Renders GridList of Clips
            setCurrentClipPage(0);
            setDisplayedClipList(allClipsData[0]);

            setIsLoading(false)
        }

        const setSummaryDialogData = async () => {
            const replayRequestId = stateParams.data.ReplayId;
            const eventName = stateParams.data.Event;
            const programName = stateParams.data.Program;

            const replayRequest = await query('get', 'api', `replay/program/${programName}/event/${eventName}/replayid/${replayRequestId}`, {disableLoader: true});
            let replayParams = {};
            replayParams.data = stateParams.data;
            replayParams.replayDetails = {};
            replayParams.replayDetails.data = replayRequest.data;
            let replayDetailsParsed = parseReplayDetails(replayRequest.data, stateParams.data)

            setCompleteReplayRequest(replayDetailsParsed);
        }

        const initializeReplayClipPreview = async () => {
            // Load the Event info from API
            const replayRequestId = stateParams.data.ReplayId;
            const audioTrack = stateParams.data.AudioTrack
            const eventName = stateParams.data.Event
            const programName = stateParams.data.Program

            setIsLoading(true)

            const latestEvent = await getLatestEventState({"Name": eventName, "Program": programName})

            //Clear out any Feature filters set
            setFilterValues([])

            if (latestEvent !== undefined) {
                setOriginalEventData(latestEvent)

                setSelectedAudioTrack(audioTrack)
                let profileRes = await query('get', 'api', `profile/${latestEvent.Profile}`, {disableLoader: true});
                profileRes = profileRes.data;
                setIsOptimizerConfiguredInProfile(_.get(profileRes, 'Optimizer.Name') !== undefined ? true : false)

                setProfileClassifier(profileRes.Classifier.Name);

                let response = await query('get', 'api-data-plane', `event/${eventName}/program/${programName}/profileClassifier/${profileRes.Classifier.Name}/track/${audioTrack}/replay/${replayRequestId}/segments/v2`,
                    {
                        limit: MAX_CLIPS,
                        LastEvaluatedKey: "",
                        disableLoader: true
                    }
                );
                
                setNextReplaysToken(_.get(response, 'LastEvaluatedKey'));

                const segments = _.get(response, 'data');
                
                if (segments !== undefined) {
                    if (_.size(segments) > 0) {
                        setSelectedCard(segments[0]);
                    }

                    // The First Clip gets selected by default.
                    _.forEach(segments, (allc, i) => {
                        allc.id = uuidv1()
                        allc.selected = i === 0;
                    });

                    if (_.size(segments) > 0) {
                        await Promise.all([
                            getOptimizedRangeEvents(segments[0], latestEvent, profileRes.Classifier.Name),
                            getOriginalRangeEvents(segments[0], latestEvent, profileRes.Classifier.Name),
                            getClipReviewFeedback(segments[0], latestEvent, profileRes.Classifier.Name)
                        ])
                    }

                    // Renders GridList of Clips
                    setAllClips([segments]);
                    ////console.log([segments]);
                    setCurrentClipPage(0);
                    setTotalClipPages(0);
                    
                    //setTotalClipPages(nextReplaysToken !== "" || nextReplaysToken !== undefined ? 1 : 0);
                    //setTotalClipPages(nextReplaysToken !== "" || nextReplaysToken !== undefined ? 1 : 0);
                    setDisplayedClipList(segments);
                }
            }
            setIsLoading(false);
        }

        const fetchMoreClips = async () => {

            if (currentClipPage === totalClipPages && stateParams.mode !== "EventClips") {
                setIsClipsLoading(true);
                // Load the Event info from API
                const replayRequestId = stateParams.data.ReplayId;
                const audioTrack = stateParams.data.AudioTrack
                const eventName = stateParams.data.Event
                const programName = stateParams.data.Program

                let response = await query('get', 'api-data-plane', `event/${eventName}/program/${programName}/profileClassifier/${profileClassifier}/track/${audioTrack}/replay/${replayRequestId}/segments/v2`,
                    {
                        limit: MAX_CLIPS,
                        LastEvaluatedKey: nextReplaysToken + 1,
                        disableLoader: true
                    }
                );

                const segments = _.get(response, 'data');
                
                if (segments.length > 0) {
                    setNextReplaysToken(_.get(response, 'LastEvaluatedKey'));

                    if (_.size(segments) > 0) {
                        setSelectedCard(segments[0]);
                    }

                    // The First Clip gets selected by default.
                    _.forEach(segments, (allc, i) => {
                        allc.id = uuidv1()
                        allc.selected = i === 0;
                    });

                    // Renders GridList of Clips
                    let clipsUpdated = allClips;
                    clipsUpdated.push(segments);
                    setAllClips(clipsUpdated);
                    setDisplayedClipList(clipsUpdated[currentClipPage + 1]);
                    setCurrentClipPage(currentClipPage + 1);
                    setTotalClipPages(currentClipPage + 1);


                    if (_.size(segments) > 0) {
                        await Promise.all([
                            getOptimizedRangeEvents(segments[0], originalEventData, profileClassifier),
                            getOriginalRangeEvents(segments[0], originalEventData, profileClassifier),
                            getClipReviewFeedback(segments[0], originalEventData, profileClassifier)
                        ])
                    }
                }
                setIsClipsLoading(false);
            }
            else {
                setDisplayedClipList(allClips[currentClipPage + 1]);
                setCurrentClipPage(currentClipPage + 1);
            }
        }


        const getOptimizedRangeEvents = async (clipInfo, eventData, classifier, track = undefined) => {

            const audioTrack = track === undefined ? selectedAudioTrack : track

            const clipStart = clipInfo.StartTime
            let duration = 0
            if (clipInfo.hasOwnProperty("OptimizedDurationPerTrack")) {
                let tmpd = clipInfo.OptimizedDurationPerTrack.filter(el => {
                    return el[audioTrack]
                })
                duration = tmpd.length > 0 ? tmpd[0][audioTrack] : 0
            }

            if (duration === 0) {
                return null; // We should never have this. If we do, exit
            }


            const event = eventData.Name;
            const program = eventData.Program;


            //let profileRes = await API.get('api', `profile/${eventData.Profile}`);
            //let profileClassifier = profileRes.Classifier.Name;

            let profileClassifier = classifier;
            let response = await query('get', 'api-data-plane', `event/${event}/program/${program}/clipstart/${clipStart}/clipduration/${duration}/track/${audioTrack}/classifier/${profileClassifier}/opt/previewinfo`,
                {disableLoader: true});
            response = response.data;

            // If Optimization hasn't completed, the state would be incomplete
            if (response != null) {
                setOptimizedRangeEvents(response.RangeEvents)
                setOptimizedClipFeatures(response.Features)
                setOptimizedClipFeatureLabels(response.FeatureLabels)


                // Store a Copy of the Feature Labels. This is Immutable and will be used for Filtering
                const tmpFeatures = []
                tmpFeatures.push(...response.Features)
                setOptimizedClipFeaturesRoot(tmpFeatures)


                let ticks = []
                let index = 0.0
                if (tmpFeatures.length > 0) {
                    while (index <= tmpFeatures[tmpFeatures.length - 1].featureAt) {
                        ticks.push(parseFloat(index.toFixed(1)))
                        index = parseFloat(index.toFixed(1)) + 1
                    }
                    setOptimizedClipFeaturesTicks(ticks)
                }


                setOptimizedRangeEventsCharts(response.RangeEventsChart)
                setOptimizedPluginLabels(response.RangeLabels)
                setOptimizedClipLocation(response.OptimizedClipLocation)
            }

            return "OK"
        }

        const getOriginalRangeEvents = async (clipInfo, eventData, classifier, track = undefined) => {
            const clipStart = clipInfo.StartTime
            const duration = clipInfo.OrigLength
            const event = eventData.Name
            const program = eventData.Program

            const audioTrack = track === undefined ? selectedAudioTrack : track

            let response = await query('get', 'api-data-plane',
                `event/${event}/program/${program}/clipstart/${clipStart}/clipduration/${duration}/track/${audioTrack}/classifier/${classifier}/org/previewinfo`,
                {disableLoader: true});
            response = response.data;


            if (response !== undefined) {
                setOriginalRangeEvents(response.RangeEvents)
                setOriginalClipFeatures(response.Features)
                setOriginalClipFeatureLabels(response.FeatureLabels)

                // Store a Copy of the Feature Labels. This is Immutable and will be used for Filtering
                const tmpFeatures = []
                tmpFeatures.push(...response.Features)
                setOriginalClipFeaturesRoot(tmpFeatures)

                let ticks = []
                let index = 0.0

                if (tmpFeatures.length > 0) {
                    while (index <= tmpFeatures[tmpFeatures.length - 1].featureAt) {
                        ticks.push(parseFloat(index.toFixed(1)))
                        index = parseFloat(index.toFixed(1)) + 1
                    }
                    setOriginalClipFeaturesTicks(ticks)
                }

                setOriginalRangeEventsCharts(response.RangeEventsChart);
                setOriginalPluginLabels(response.RangeLabels);
                setOriginalClipLocation(response.OriginalClipLocation);
            }
        }

        React.useEffect(() => {

            let featureLabelColors = {}
            _.forEach(clipFeatureLabels, label => {
                featureLabelColors[label] = randomColor({
                    luminosity: 'light',
                    format: 'rgb'
                });
            })

            setFeatureLabelColors(featureLabelColors)

        }, [clipFeatureLabels]);

        React.useEffect(() => {

            let featureLabelColors = {}

            // Only if the Optimized Segments were not generated,
            // use the Original Clip Features plus colors.
            if (_.size(clipFeatureLabels) === 0) {
                _.forEach(originalClipFeatureLabels, label => {
                    featureLabelColors[label] = randomColor({
                        luminosity: 'light',
                        format: 'rgb'
                    });
                })

                setFeatureLabelColors(featureLabelColors)
            }

        }, [originalClipFeatureLabels]);

        React.useEffect(() => {

            let pluginLabelColors = {}
            _.forEach(pluginLabels, label => {
                pluginLabelColors[label] = randomColor({
                    luminosity: 'light',
                    format: 'rgb'
                });
            })

            setRangeEventColors(pluginLabelColors)
        }, [pluginLabels]);


        // This callback gets called whenever a card is clicked in the Video Preview list
        // Handles the Highlighting of the selected card and deselects all the other cards.
        // Also Loads the Original and Optimized data for the selected Clip
        const handleHighlightCard = async (cardId) => {
            //console.log(cardId);
            _.forEach(allClips, async (page) => {
                _.forEach(page, async (allc) => {
                    if (allc.id === cardId) {
                        setSelectedCard(allc)

                        setIsLoading(true)
                        resetThumbs()
                        resetThumbColor()


                        //Clear of Filters
                        setOptimizedClipFeatures([])
                        setOriginalClipFeatures([])
                        setOriginalClipFeaturesRoot([])
                        setOptimizedClipFeaturesRoot([])
                        setFilterValues([])

                        // Load Clip Metadata for selected Clip
                        await Promise.all([getOptimizedRangeEvents(allc, originalEventData, profileClassifier), getOriginalRangeEvents(allc, originalEventData, profileClassifier)])

                        // Get Clip Feedback Info every time Audio Track is changed
                        getClipReviewFeedback(allc, originalEventData, profileClassifier)

                        setIsLoading(false)
                    }
                })
            })

            //console.log(displayedClipList);

            // Handle Highlighting
            _.forEach(allClips, (page) => {
                _.forEach(page, allc => {
                    allc.id === cardId ? allc.selected = true : allc.selected = false
                })
            });

            setAllClips(_.cloneDeep(allClips))
            
            _.forEach(displayedClipList, allc => {
                allc.id === cardId ? allc.selected = true : allc.selected = false
            })
            setDisplayedClipList(displayedClipList)
        }

        const handleAudioTrackChange = async (event) => {
            setSelectedAudioTrack(event.target.value);

            setIsLoading(true)
            resetThumbs()
            resetThumbColor()

            //Clear of Filters
            setFilterValues([])
            setOptimizedClipFeatures([])
            setOptimizedClipFeaturesRoot([])

            const origEventData = clipPreviewMode === "EventClips" ? _.get(stateParams, 'origEventData') : originalEventData
            const res = await getOptimizedRangeEvents(selectedCard, origEventData, profileClassifier, event.target.value)

            setOriginalClipFeatures([])
            setOriginalClipFeaturesRoot([])
            await getOriginalRangeEvents(selectedCard, origEventData, profileClassifier, event.target.value)

            // Get Clip Feedback Info every time Audio Track is changed
            await getClipReviewFeedback(selectedCard, origEventData, profileClassifier, event.target.value)

            setIsLoading(false)
        }

        React.useEffect(() => {
            (async () => {
                const origEventData = clipPreviewMode === "EventClips" ? _.get(stateParams, 'origEventData') : originalEventData
                if (origEventData.Program !== undefined && (originalAction || optimizedAction)){
                    
                    //console.log("React.useEffect");
                    if (originalAction)
                        setThumbsUpOrigLoading(true)
                    else if (optimizedAction)
                        setThumbsUpOptoLoading(true)

                    let feedback = await getClipFeedbackState()
                    const res = await saveThumbsUpFeedback(feedback)
                    
                    
                    if (originalAction){
                        setThumbsUpOrigLoading(false)
                        setOriginalAction(false)
                    }
                    if (optimizedAction){
                        setThumbsUpOptoLoading(false)
                        setOptimizedAction(false)    
                    }

            }

            })();

        }, [originalThumbsUp, optimizedThumbsUp, originalThumbsDown, optimizedThumbsDown, originalAction, optimizedAction ]);

        /*React.useEffect(() => {
            (async () => {
                const origEventData = clipPreviewMode === "EventClips" ? _.get(stateParams, 'origEventData') : originalEventData
                if (origEventData.Program !== undefined && optimizedAction){
                    setThumbsUpOptoLoading(true)

                    let feedback = await getClipFeedbackState()
                    const res = await saveThumbsUpFeedback(feedback)

                    if (res.success) {
                        setOptimizedThumbsUpColor(optimizedThumbsUp ? "green": "")
                        setOptimizedThumbsDownColor("")
                        setOptimizedFeedbackDetail('')
                        setOptimizedAction(false)
                    }
                    setThumbsUpOptoLoading(false)
            }

            })();

        }, [optimizedThumbsUp]); */

        const getClipReviewFeedback = async (clipInfo, eventData, classifier, track = undefined) => {
            const clipStart = clipInfo.StartTime
            const event = eventData.Name
            const program = eventData.Program

            //console.log("getClipReviewFeedback");

            const audioTrack = track === undefined ? selectedAudioTrack : track

            setOriginalAction(false)
            setOptimizedAction(false)

            //let response = await query('get', 'api-data-plane', `clip/preview/program/${program}/event/${event}/classifier/${classifier}/start/${clipStart}/track/${audioTrack}/reviewer/${authenticatedUserName}/feedback`,
            let response = await query('get', 'api-data-plane', `clip/preview/program/${program}/event/${event}/classifier/${classifier}/start/${clipStart}/track/${audioTrack}/feedback`,
                {disableLoader: true});
            response = response.data;

            if (response !== undefined) {
                if (response.hasOwnProperty('PK')) {
                    
                    if (response.OptimizedFeedback.Feedback === 'Like') {
                        setOptimizedThumbsUp(true)
                        setOptimizedThumbsUpColor("green")
                        setOptimizedThumbsDownColor("")
                    }
                    else if (response.OptimizedFeedback.Feedback === 'Dislike') {

                        setOptimizedThumbsUp(false)
                        setOptimizedThumbsDown(true)
                        setOptimizedFeedbackDetail(response.OptimizedFeedback.FeedbackDetail)
                        setOptimizedThumbsUpColor("")
                        setOptimizedThumbsDownColor("red")
                    }
                    else{
                        setOptimizedThumbsUp(false)
                        setOptimizedThumbsDown(false)
                        setOptimizedFeedbackDetail('')
                        setOptimizedThumbsUpColor("")
                        setOptimizedThumbsDownColor("")

                    }

                    if (response.OriginalFeedback.Feedback === 'Like') {
                        setOriginalThumbsUp(true)
                        setOriginalThumbsUpColor("green")
                        setOriginalThumbsDownColor("")
                    }
                    else if (response.OriginalFeedback.Feedback === 'Dislike') {

                        setOriginalThumbsUp(false)
                        setOriginalThumbsDown(true)
                        setOriginalFeedbackDetail(response.OriginalFeedback.FeedbackDetail)
                        setOriginalThumbsUpColor("")
                        setOriginalThumbsDownColor("red")
                    }
                    else{
                        setOriginalThumbsUp(false)
                        setOriginalThumbsDown(false)
                        setOriginalFeedbackDetail("")
                        setOriginalThumbsUpColor("")
                        setOriginalThumbsDownColor("")
                    }
                }
            }
        }

        const resetThumbColor = () => {

            setOriginalThumbsUpColor("")
            setOriginalThumbsDownColor("")
            setOptimizedThumbsDownColor("")
            setOptimizedThumbsUpColor("")
        }

        const resetThumbs = () => {
            setOriginalThumbsUp(false)
            setOptimizedThumbsUp(false)
            setOriginalFeedbackDetail('')
            setOptimizedFeedbackDetail('')

        }

        

        const handleOriginalThumbUp = async () => {
            setCurrentFeedbackMode('Original')
            setOriginalThumbsUp(!originalThumbsUp)
            setOriginalThumbsUpColor(originalThumbsUp ? "" : "green")

            setOriginalThumbsDownColor("")
            setOriginalThumbsDown(false)

            setOriginalFeedbackDetail("")

            setOriginalAction(true)
            
            
        }

        const handleOptimalThumbUp = async () => {
            setCurrentFeedbackMode('Optimized')            
            setOptimizedThumbsUp(!optimizedThumbsUp)
            setOptimizedThumbsUpColor(optimizedThumbsUp ? "" : "green")

            setOptimizedThumbsDown(false)
            setOptimizedThumbsDownColor("")

            setOptimizedFeedbackDetail("")

            setOptimizedAction(true)

            
        }

        const handleOriginalThumbDown = () => {
            setCurrentFeedbackMode('Original')
            setClipPreviewOpen(true);
        }

        const handleOptimalThumbDown = () => {
            setCurrentFeedbackMode('Optimized')
            setClipPreviewOpen(true);
        }

        const getClipFeedbackState = async () => {
            let feedbackState = {}

            const origEventData = clipPreviewMode === "EventClips" ? _.get(stateParams, 'origEventData') : originalEventData
            feedbackState.Event = origEventData.Name
            feedbackState.Program = origEventData.Program

            feedbackState.Classifier = profileClassifier

            feedbackState.StartTime = selectedCard.StartTime
            feedbackState.AudioTrack = selectedAudioTrack
            feedbackState.Reviewer = authenticatedUserName
            feedbackState.IsOptimizerConfiguredInProfile = isOptimizerConfiguredInProfile

            if (originalAction || currentFeedbackMode === "Original")
                feedbackState.ActionSource = "Original"
            else if (optimizedAction || currentFeedbackMode === "Optimized")
                feedbackState.ActionSource = "Optimized"

            feedbackState.OriginalFeedback = {}
            feedbackState.OptimizedFeedback = {}
            //console.log(`originalThumbsDown=${originalThumbsDown}`);
            if (originalThumbsDown){
                feedbackState.OriginalFeedback.Feedback = 'Dislike'
                feedbackState.OriginalFeedback.FeedbackDetail = originalFeedbackDetail

                if (originalDislikeResetCheckBoxState){
                    feedbackState.OriginalFeedback.Feedback = '-'
                    feedbackState.OriginalFeedback.FeedbackDetail = ''

                    setOriginalDislikeResetCheckBoxState(false)
                }
            }
            //console.log(`optimizedThumbsDown=${optimizedThumbsDown}`);

            if (optimizedThumbsDown){
                feedbackState.OptimizedFeedback.Feedback = 'Dislike'
                feedbackState.OptimizedFeedback.FeedbackDetail = optimizedFeedbackDetail

                if (optoDislikeResetCheckBoxState){
                    feedbackState.OptimizedFeedback.Feedback = '-'
                    feedbackState.OptimizedFeedback.FeedbackDetail = ''

                    setoptoDislikeResetCheckBoxState(false)
                }
            }
            
            //console.log(`originalThumbsUp=${originalThumbsUp}`);
            if (originalThumbsUp){
                feedbackState.OriginalFeedback.Feedback = 'Like'
                feedbackState.OriginalFeedback.FeedbackDetail = '-'
            }   
            //console.log(`optimizedThumbsUp=${optimizedThumbsUp}`);
            if (optimizedThumbsUp){
                feedbackState.OptimizedFeedback.Feedback = 'Like'
                feedbackState.OptimizedFeedback.FeedbackDetail = '-'
            }

            if (!originalThumbsDown && !originalThumbsUp){
                feedbackState.OriginalFeedback.Feedback = '-'
                feedbackState.OriginalFeedback.FeedbackDetail = '-'
            }

            if (!optimizedThumbsDown && !optimizedThumbsUp){
                feedbackState.OptimizedFeedback.Feedback = '-'
                feedbackState.OptimizedFeedback.FeedbackDetail = '-'
            }
                
            
            //console.log(feedbackState);
            return feedbackState
        }

        const saveThumbsUpFeedback = async (feedback) => {
            return await query('post', 'api-data-plane', `clip/preview/feedback`, {
                body: feedback,
                disableLoader: true
            });
        }
        const handleFeedbackCancel = () => {
            if (currentFeedbackMode === 'Original') {
                setOriginalDislikeResetCheckBoxState(false)
                setOriginalFeedbackDetail("")
                setOriginalAction(false)
            }
            else if (currentFeedbackMode === 'Optimized') {
                setoptoDislikeResetCheckBoxState(false)
                setOptimizedFeedbackDetail("")
                setOptimizedAction(false)
            }
        }
        const handleFeedbackSuccess = (feedbackDetail) => {

            if (currentFeedbackMode === 'Original') {

                // User chose to remove the Dislike
                if (originalDislikeResetCheckBoxState){
                    setOriginalThumbsDownColor("") 
                    setOriginalThumbsDown(false)
                    setOriginalFeedbackDetail("")
                    setOriginalDislikeResetCheckBoxState(false)
                }
                else{
                    setOriginalThumbsDownColor("red")
                    setOriginalThumbsDown(true)
                    setOriginalFeedbackDetail(feedbackDetail)
                }

                // Triggers useEffect to persist to DB
                setOriginalAction(true)
                setOriginalThumbsUpColor("")
                setOriginalThumbsUp(false)
                
            }
            else if (currentFeedbackMode === 'Optimized') {
                if (optoDislikeResetCheckBoxState){
                    setOptimizedThumbsDown(false)
                    setOptimizedThumbsDownColor("") 
                    setOptimizedFeedbackDetail("")
                    setoptoDislikeResetCheckBoxState(false)
                }
                else{
                    setOptimizedThumbsDown(true)
                    setOptimizedThumbsDownColor("red")
                    setOptimizedFeedbackDetail(feedbackDetail)
                }   

                // Triggers useEffect to persist to DB
                setOptimizedAction(true)
                setOptimizedThumbsUpColor("")
                setOptimizedThumbsUp(false)
                
            }
        }

        

        const handleFeedbackFailure = () => {
            //console.log('failure');
            if (currentFeedbackMode === 'Original')
                setOriginalThumbsDownColor("") // This will Clear both ThumbsUp and Down
            else if (currentFeedbackMode === 'Optimized')
                setOptimizedThumbsDownColor("")  // This will Enable ThumbsDown
        }

        const handleFeedbackChange = (e) => {
            //console.log('change');
            if (currentFeedbackMode === 'Original')
                setOriginalFeedbackDetail(e.target.value)
            else if (currentFeedbackMode === 'Optimized')
                setOptimizedFeedbackDetail(e.target.value)
        }

        const backFillTimesForFeatures = (filteredFeatures, features, featuresRoot, featureName) => {
            // BackFill Dummy values to retain the X - Axis values
            // For example, if Topview starts at 10 Secs and ends at 14 secs,
            // and clip duration is 20 secs, backfill dummy values from 0 to 10
            // and 14 to 20 secs.
            const startsAt = filteredFeatures[0].featureAt
            const endsAt = filteredFeatures[filteredFeatures.length - 1].featureAt


            // BackFill from 0 Secs to the Min
            let index = 0.0
            while (index <= startsAt) {
                features.push({
                    [featureName]: 0,
                    "featureAt": index
                })
                index = parseFloat(index.toFixed(1)) + 0.2
            }

            // BackFill from the current Max Time to the End of Clip
            let index1 = endsAt
            const clipDuration = featuresRoot[featuresRoot.length - 1].featureAt
            while (index1 < clipDuration) {
                features.push({
                    [featureName]: 0,
                    "featureAt": index1
                })
                index1 = parseFloat(index1.toFixed(1)) + 0.2
            }

            // Retain the End time of the Clip time
            features.push({
                [featureName]: 0,
                "featureAt": featuresRoot[featuresRoot.length - 1].featureAt
            })

        }

        const handleOptimizeFilterChange = (e) => {

            // For a Multi Select, the Value wil be an Array
            let filter = e.target.value;
            let tmpFltrValues = []
            _.forEach(filter, f => {
                tmpFltrValues.push(f)
            })
            setFilterValues(tmpFltrValues)

            // Refresh the Feature Chart based on filterProps
            // We create a new Array based on the FilerArray
            // and the Feature Data we got from API
            //////////////////////// Optimized //////////////////////
            const optimizedFilteredFeatures = []
            _.forEach(tmpFltrValues, vv => {
                let ab = _.filter(optimizedClipFeaturesRoot, feature => {
                    return feature.hasOwnProperty(vv)
                })
                optimizedFilteredFeatures.push(...ab)

                if (ab.length > 0)
                    backFillTimesForFeatures(ab, optimizedFilteredFeatures, optimizedClipFeaturesRoot, vv)


            })

            setOptimizedClipFeatures(_.sortBy(optimizedFilteredFeatures, 'featureAt'))
            //////////////////////// Optimized //////////////////////

            //////////////////////// Original //////////////////////
            const originalFilteredFeatures = []
            _.forEach(tmpFltrValues, vv => {
                let ab = _.filter(originalClipFeaturesRoot, feature => {
                    return feature.hasOwnProperty(vv)
                })
                originalFilteredFeatures.push(...ab)

                if (ab.length > 0)
                    backFillTimesForFeatures(ab, originalFilteredFeatures, originalClipFeaturesRoot, vv)
            })


            setOriginalClipFeatures(_.sortBy(originalFilteredFeatures, 'featureAt'))
            //////////////////////// Original //////////////////////
        }

        const handleOptimizeDeleteChip = (chipToDelete) => {
            const tmpFilterValues = _.filter(filterValues, item => {
                return item !== chipToDelete;
            });
            //
            setFilterValues(tmpFilterValues)

            //////////////////////// Optimized //////////////////////
            if (tmpFilterValues.length === 0)
                setOptimizedClipFeatures(optimizedClipFeaturesRoot)
            else {
                const optimizedFilteredFeatures = []
                _.forEach(tmpFilterValues, vv => {
                    let ab = _.filter(optimizedClipFeaturesRoot, feature => {
                        return feature.hasOwnProperty(vv)
                    })
                    optimizedFilteredFeatures.push(...ab)

                    if (ab.length > 0)
                        backFillTimesForFeatures(ab, optimizedFilteredFeatures, optimizedClipFeaturesRoot, vv)
                })


                setOptimizedClipFeatures(_.sortBy(optimizedFilteredFeatures, 'featureAt'))
            }
            //////////////////////// Optimized //////////////////////

            //////////////////////// Original //////////////////////
            if (tmpFilterValues.length === 0)
                setOriginalClipFeatures(originalClipFeaturesRoot)
            else {
                const originalFilteredFeatures = []
                _.forEach(tmpFilterValues, vv => {
                    let ab = _.filter(originalClipFeaturesRoot, feature => {
                        return feature.hasOwnProperty(vv)
                    })
                    originalFilteredFeatures.push(...ab)

                    if (ab.length > 0)
                        backFillTimesForFeatures(ab, originalFilteredFeatures, originalClipFeaturesRoot, vv)
                })
                setOriginalClipFeatures(_.sortBy(originalFilteredFeatures, 'featureAt'))
            }
            //////////////////////// Original //////////////////////
        }

        const handleReplayViewDialogClose = () => {
            setReplayViewDialogOpen(false)
        }

        const showReplayRequest = async () => {
            await setSummaryDialogData();
            setReplayViewDialogOpen(true)
        }

        const handleClipsBack = () => {
            setDisplayedClipList(allClips[currentClipPage - 1]);
            setCurrentClipPage(currentClipPage - 1);
        }

        const getClipsWidth = () => {
            // clips preview width defined by the number of clips, and does not shrink while rendering more
            return displayedClipList && (_.isEmpty(displayedClipList) === true && _.isEmpty(allClips[currentClipPage - 1]) !== true) ?
                _.min([(_.size(allClips[currentClipPage - 1])), 10]) :
                _.min([(_.size(displayedClipList)), 10])
        }


        const handlePlayHighlightClick = async(event) => {

            setHighlightClipOpen(true)
            setLoadingHighlightClipVideo(true)

            const replayRequestId = stateParams.data.ReplayId;
            const eventName = stateParams.data.Event;
            const programName = stateParams.data.Program;

            const replayRequest = await query('get', 'api', `replay/program/${programName}/event/${eventName}/replayid/${replayRequestId}`, {disableLoader: true});
            const replay_details = replayRequest.data
            setHighlightClipVideoUrl(replay_details["PreviewVideoUrl"])

            setLoadingHighlightClipVideo(false)

        }

        const handleHiglightClipDialogClose = () => {
            setHighlightClipOpen(false)
        }

        return (
            <Box pt={1} pb={10}>
                <ClipPreviewModal
                    open={clipPreviewOpen}
                    setOpen={setClipPreviewOpen}
                    title={currentFeedbackMode === "Original" ? "Original Segment Quality Feedback" : "Optimized Segment Quality Feedback"}
                    clipState={getClipFeedbackState}
                    onSuccessFunction={handleFeedbackSuccess}
                    onFailureFunction={handleFeedbackFailure}
                    feedbackMode={currentFeedbackMode}
                    feedback={currentFeedbackMode === 'Original' ? originalFeedbackDetail : optimizedFeedbackDetail}
                    onFeedbackChange={handleFeedbackChange}
                    resetOriginalChecked={originalDislikeResetCheckBoxState}
                    resetOptimizedChecked={optoDislikeResetCheckBoxState}
                    resetCheckedChangeHandler={handleDislikeResetCheckBoxChange}
                    onCancelFunction={handleFeedbackCancel}
                    SetOriginalThumbsUp={setOriginalThumbsUp}
                    SetOptimizedThumbsUp={setOptimizedThumbsUp}
                    SetOriginalThumbsDown={setOriginalThumbsDown}
                    SetOptimizedThumbsDown={setOptimizedThumbsDown}
                />

                {completeReplayRequest &&
                <ReplayViewDialog
                    onReplayViewDialogClose={handleReplayViewDialogClose}
                    open={replayViewDialogOpen}
                    dialogParams={completeReplayRequest}
                />}
                <Grid container direction="column" spacing={5}>
                    <Grid container item direction="row" justify="space-between">
                        <Grid item sm={7}>
                            <Breadcrumbs>
                                <Link color="inherit" component="button" variant="subtitle1" onClick={goBack}>
                                    {stateParams.back.name}
                                </Link>
                                {
                                    stateParams.mode === "EventClips" ?
                                        <Grid item>
                                            <Typography
                                                color="textPrimary">{`Clip Preview / Program - ${originalEventData.Program === undefined ? '' : originalEventData.Program} / Event- ${originalEventData.Name === undefined ? '' : originalEventData.Name}`}
                                            </Typography>
                                        </Grid> : stateParams.mode === "ReplayClips" &&

                                        <Grid item>
                                            <Typography
                                                color="textPrimary">{`Replay Clips / Program - ${stateParams.data.Program === undefined ? '' : stateParams.data.Program} / Event- ${stateParams.data.Event === undefined ? '' : stateParams.data.Event}`}
                                            </Typography>
                                        </Grid>
                                }
                            </Breadcrumbs>
                        </Grid>
                        {
                            stateParams.mode !== "EventClips" &&
                            <Grid container item direction={"row"} alignItems="center" justify="flex-end" sm={2}
                                  spacing={2}>
                                <Grid item>
                                    <IconButton size="small" color="secondary"
                                                onClick={handlePlayHighlightClick}>
                                        <Tooltip title="Play highlight MP4 clip">
                                            <PlayCircleFilledIcon  
                                                color={"primary"} 
                                                style={{ verticalAlign: "middle", cursor: "pointer"}}
                                                disabled={highlightClipVideoUrl === "" ? true : false}
                                            />
                                        </Tooltip>
                                    </IconButton>
                                </Grid>
                                <Grid item>
                                    <IconButton size="small" color="secondary"
                                                onClick={showReplayRequest}>
                                        <Tooltip title="Show Replay details">
                                            <MoreHorizIcon className={classes.iconSize}/>
                                        </Tooltip>
                                    </IconButton>
                                </Grid>
                                <Grid item>
                                    <IconButton size="small" color="secondary"
                                                onClick={initializeReplayClipPreview}>
                                        <Tooltip title="Fetch more Replay clips">
                                            <AutorenewIcon className={classes.iconSize}/>
                                        </Tooltip>
                                    </IconButton>
                                </Grid>
                            </Grid>
                        }
                    </Grid>
                    <Grid container item direction="column" spacing={5}>
                        {allClips && _.isEmpty(allClips[0]) === true && isLoading !== true ?
                            <Box pt={3} display="flex" justifyContent="center">
                                <Typography variant={"h6"}>
                                    Replay hasn't found any clips just yet. Try refreshing in a few moments.
                                </Typography>
                            </Box> :
                            displayedClipList == null && isLoading ?
                                <div>
                                    <Backdrop open={true} className={classes.backdrop}>
                                        <CircularProgress color="inherit"/>
                                    </Backdrop>
                                </div> :
                                _.size(displayedClipList) > 0 && currentClipPage != null && totalClipPages != null &&
                                <Grid container item direction="column" spacing={2} justify="center" alignItems="center">
                                    <Grid container item direction="row" spacing={3} alignItems="center"
                                          style={{minHeight: "4vw"}}>
                                        <Grid item>
                                            <IconButton
                                                disabled={currentClipPage === 0}
                                                onClick={() => {
                                                    handleClipsBack()
                                                }}
                                            >
                                                <ArrowBackIosIcon fontSize={'large'}/>
                                            </IconButton>
                                        </Grid>
                                        <Grid container item direction="row" sm={getClipsWidth()} justify="center">
                                            <Grid item>
                                                <GridList className={classes.gridList} cols={10} ref={gridListRef}>
                                                    {_.map(displayedClipList, (clipDetail, index) => {
                                                        return <ThumbnailCard
                                                            key={index}
                                                            ClipDetail={clipDetail}
                                                            onHighlightCard={handleHighlightCard}
                                                            highlightCard={clipDetail.selected}
                                                            OriginalEventData={originalEventData}
                                                            IsOptimizerConfiguredInProfile={isOptimizerConfiguredInProfile}
                                                        />
                                                    })
                                                    }
                                                </GridList>
                                            </Grid>
                                        </Grid>
                                        <Grid item>
                                            {
                                                isClipsLoading === true && allClips[currentClipPage] ?
                                                    <div style={{paddingLeft: 10}}>
                                                        <CircularProgress color="inherit"/>
                                                    </div>
                                                    :
                                                    <IconButton
                                                        disabled={
                                                            ((nextReplaysToken === "" || nextReplaysToken === undefined) && currentClipPage === totalClipPages && stateParams.mode !== "EventClips") ||
                                                            (stateParams.mode === "EventClips" && currentClipPage === totalClipPages - 1)
                                                        }
                                                        onClick={fetchMoreClips}
                                                    >
                                                        <ArrowForwardIosIcon fontSize={'large'}/>
                                                    </IconButton>
                                            }

                                        </Grid>
                                    </Grid>
                                    <Grid item container direction="row">
                                        <Grid item sm={1}>
                                            {
                                                clipPreviewMode === "EventClips" ?
                                                    <FormControl fullWidth size="small" variant="outlined">
                                                        <FormLabel style={{paddingBottom: 5}}>Audio
                                                            Track</FormLabel>
                                                        <Select
                                                            value={selectedAudioTrack}
                                                            onChange={handleAudioTrackChange}
                                                        >
                                                            {!_.isEmpty(originalEventData) &&

                                                            _.map(originalEventData.AudioTracks, (audioTrackNo) => {
                                                                return <MenuItem
                                                                    value={audioTrackNo}>{audioTrackNo}</MenuItem>
                                                            })
                                                            }
                                                        </Select>
                                                    </FormControl>
                                                    :
                                                    <Typography
                                                        color="textPrimary">{`Audio Track ${selectedAudioTrack}`}
                                                    </Typography>
                                            }
                                        </Grid>
                                    </Grid>
                                    {
                                        isLoading ?
                                            <div>
                                                <Backdrop open={true} className={classes.backdrop}>
                                                    <CircularProgress color="red"/>
                                                </Backdrop>
                                            </div> :
                                            <Grid container item direction="column" spacing={5}>
                                                <Grid container item direction="row" justify="space-between">
                                                    <Grid item xs={isOptimizerConfiguredInProfile ? 5 : 8} style={{textAlign: "-webkit-center", alignSelf: "center"}}>
                                                        {
                                                            originalEventData.GenerateOrigClips ? 
                                                            <ClipPlayer
                                                                Title="Original"
                                                                HandleOriginalThumbUp={handleOriginalThumbUp}
                                                                HandleOriginalThumbDown={handleOriginalThumbDown}
                                                                ThumbsUpColor={originalThumbsUpColor}
                                                                ThumbsDownColor={originalThumbsDownColor}
                                                                ClipLocation={originalClipLocation}
                                                                Mode={clipPreviewMode}
                                                                IsOriginalLoading={thumbsUpOrigLoading}
                                                                
                                                            /> :
                                                            <ClipPlaceholder 
                                                                Title=""
                                                                Message= "Original segment clip generation disabled"
                                                            />
                                                        }   
                                                        
                                                    </Grid>
                                                    <Grid item xs={5} style={{alignSelf: "center", textAlign: "-webkit-center",}}>
                                                    {
                                                        (originalEventData.GenerateOptoClips && isOptimizerConfiguredInProfile ) ?
                                                        <ClipPlayer
                                                            Title="Optimized"
                                                            HandleOriginalThumbUp={handleOptimalThumbUp}
                                                            HandleOriginalThumbDown={handleOptimalThumbDown}
                                                            ThumbsUpColor={optimizedThumbsUpColor}
                                                            ThumbsDownColor={optimizedThumbsDownColor}
                                                            ClipLocation={optimizedClipLocation}
                                                            Mode={clipPreviewMode}
                                                            IsOptimizedLoading={thumbsUpOptoLoading}
                                                            
                                                        /> 
                                                        :
                                                        !originalEventData.GenerateOptoClips && isOptimizerConfiguredInProfile ?
                                                        <ClipPlaceholder 
                                                            Title=""
                                                            Message= "Optimized segment clip generation disabled"
                                                        />:
                                                        <></>
                                                        
                                                    }
                                                </Grid>
                                                </Grid>
                                                <Grid container item direction="row" justify="space-between">
                                                    <Grid item xs={isOptimizerConfiguredInProfile ? 5 : 8}>
                                                        <RangeBarChart
                                                            RangeEventsCharts={originalRangeEventsCharts}
                                                            PluginLabels={originalPluginLabels}
                                                            RangeEventColors={allPluginNameColor}
                                                        />
                                                    </Grid>
                                                    {isOptimizerConfiguredInProfile &&
                                                    <Grid item xs={5}>
                                                        <RangeBarChart
                                                            RangeEventsCharts={rangeEventsCharts}
                                                            PluginLabels={pluginLabels}
                                                            RangeEventColors={allPluginNameColor}
                                                        />
                                                    </Grid>
                                                    }
                                                </Grid>
                                                <Grid container item direction="row" justify="space-between">
                                                    <Grid item xs={isOptimizerConfiguredInProfile ? 5 : 8}>
                                                        <RangeTable
                                                            RangeEvents={originalRangeEvents}
                                                            RangeEventColors={allPluginNameColor}
                                                        />
                                                    </Grid>
                                                    {isOptimizerConfiguredInProfile &&
                                                    <Grid item xs={5}>
                                                        <RangeTable
                                                            RangeEvents={rangeEvents}
                                                            RangeEventColors={allPluginNameColor}
                                                        />
                                                    </Grid>
                                                    }
                                                </Grid>
                                                <Grid container item direction="row" justify="space-between">
                                                    <Grid item style={{maxWidth: "100%"}} xs={6}>
                                                        <MultiSelectWithChips
                                                            label="Plugin Filter"
                                                            options={clipFeatureLabels.length > 0 ? clipFeatureLabels : originalClipFeatureLabels}
                                                            selected={filterValues}
                                                            handleChange={handleOptimizeFilterChange}
                                                            handleDelete={handleOptimizeDeleteChip}
                                                            hasDropdownComponent={false}
                                                            fullWidth={false}
                                                        />
                                                    </Grid>
                                                </Grid>
                                                <Grid container item direction="row" justify="space-between">
                                                    <Grid item xs={isOptimizerConfiguredInProfile ? 5 : 8}>
                                                        <FeatureBarChart
                                                            Features={originalClipFeatures}
                                                            LegendHeight={20}
                                                            FeatureLabels={originalClipFeatureLabels}
                                                            FeatureLabelColors={featureLabelColors}
                                                            Ticks={originalClipFeaturesTicks}
                                                        />
                                                    </Grid>
                                                    {isOptimizerConfiguredInProfile &&
                                                    <Grid item xs={5}>
                                                        <FeatureBarChart
                                                            Features={clipFeatures}
                                                            LegendHeight={25}
                                                            FeatureLabels={clipFeatureLabels}
                                                            FeatureLabelColors={featureLabelColors}
                                                            Ticks={optimizedClipFeaturesTicks}
                                                        />
                                                    </Grid>
                                                    }
                                                </Grid>
                                            </Grid>
                                    }
                                </Grid>
                        }
                    </Grid>
                </Grid>


                <Box>
                    <Dialog
                        fullWidth
                        maxWidth="md"
                        open={highlightClipOpen}
                        onClose={handleHiglightClipDialogClose}
                        disableBackdropClick
                    >
                        <form>
                        <DialogTitle>
                            Highlights for {stateParams.data.Program}/{stateParams.data.Event}
                            
                        </DialogTitle>
                        <DialogContent>
                            {
                                loadingHighlightClipVideo ? 
                                    <div style={{paddingLeft: 10}}>
                                        <CircularProgress color="inherit"/>
                                    </div>
                                :
                                    highlightClipVideoUrl !== '' ?
                                    <ReactPlayer
                                        url={highlightClipVideoUrl}
                                        width='100%'
                                        height='500px'
                                        controls={true}
                                        playing={true}
                                        loop={true}
                                    /> : !loadingHighlightClipVideo ? 
                                        <Typography color="textPrimary">No highlight clip has been generated yet. Please try again in a while.</Typography>
                                    : <></>
                            }
                            
                        </DialogContent>
                        <DialogActions>
                            <Button color="primary" disabled={false} onClick={handleHiglightClipDialogClose}>
                                Close
                            </Button>
                        </DialogActions>
                        </form>

                    </Dialog>
                </Box>



            </Box>


            
        );
    }
;