/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import {makeStyles} from '@material-ui/core/styles';
import {Buffer} from 'buffer'
import _ from "lodash";
import {useNavigate, createSearchParams} from "react-router-dom";
import { Grid, Tooltip } from "@material-ui/core";
import {Typography} from "@material-ui/core";
import { Icon } from "@material-ui/core";
import IconButton from "@material-ui/core/IconButton";
import ChevronRightIcon from '@material-ui/icons/ChevronRight';
import CircularProgress from "@material-ui/core/CircularProgress";
import CloseIcon from '@material-ui/icons/Close';
import Button from "@material-ui/core/Button";
import { v4 as uuidv4 } from 'uuid';
import { APIHandler } from "../../common/APIHandler/APIHandler";
import Paper from '@material-ui/core/Paper';
import {Input} from "@material-ui/core";
import config from "../../config";
import { useMutation } from '@tanstack/react-query';
import { 
    getChunksAsBytes,
    getDetails,
    getObjectsInDetails,
    getSummary,
    getTitles
 } from "../../common/utils/utils";
 import GenAiSearchIcon from '../../assets/genai-search-3.svg';

const userPersonaName = "User"
const botPersonaName = "Assistant"
const useStyles = makeStyles((theme) => ({
    chatWindow: {
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
    },
    dialogue: {
        marginBottom: "3px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-start",
        overflowY: "auto",
        margin: "10px 0px",
        maxHeight: "calc(100vh - 256px)"
   },
    correspondance: {
        margin: "10px",
        width: "calc(100% - 20px)",
        padding: "0px 15px",
    },
    userPersona: {
        alignSelf: "flex-end",
        backgroundColor: "#666",
        borderRadius: "10px 0px 10px 10px",
    },
    botPersona: {
        alignSelf: "flex-start",
        backgroundColor: "#17191e",
        borderRadius: "0px 10px 10px 10px",
    },
    chatInput: {
        width: "95%",
        margin: "auto",
        padding: "10px"
    },
    root: {
        margin: "10px",
        padding: "10px 15px",
        display: 'flex',
        alignItems: 'center',
        justifyContent: "space-between",
        backgroundColor: "#666",
        position: "absolute",
        bottom: 64,
        width: "calc(100% - 75px)"
      },
      divider: {
        height: 28,
        margin: 4,
      },
}));

export const ChatWindow = (props) => {
    const classes = useStyles();
    
    const [chatContent, setChatContent] = React.useState([]);
    const [currentChat, setCurrentChat] = React.useState([]);
    const [formData, setFormData] = React.useState({ search: '' });
    const [isPending, setIsPending] = React.useState(false);
    const [currentBotMessageId, setCurrentBotMessageId] = React.useState('');
    const [isGettingDetails, setIsGettingDetails] = React.useState(false);
    const [stopLoop, setStopLoop] = React.useState(false);
    const [currentResponse, setCurrentResponse] = React.useState(null);
    const [reader, setReader] = React.useState(null);
    const navigate = useNavigate();

    const {query, streamQuery, isLoading} = APIHandler();
    const scrollableRef = React.useRef(null);

    const handleScrollTop = () => {
      const element = scrollableRef.current;
      if (element) {
        setTimeout(() => {
          element.scroll({ top: element.scrollHeight, behavior: 'smooth' });
        }, 100);
      }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        if (formData.search.length) {
            setChatContent([
            ...chatContent,
            {
                id: uuidv4(),
                from: "me",
                message: formData.search,
            },
            ]);
            setIsPending(true);
            props.setMessages([
                ...props.messages,
                {
                persona: userPersonaName,
                message: formData.search,
                },
            ])

            handleScrollTop();
            
        }
    };

    const { mutateAsync } = useMutation({
        mutationKey: ['event/search'],
        mutationFn: (query) =>
          streamQuery("post", config.lambda.REACT_APP_SEARCH_LAMBDA_URL, {
            SessionId: props.searchContext.SessionId,
            Program: props.searchContext.Program,
            Event: props.searchContext.Name,
            Query: query,
          }),
      });

    React.useEffect(() => {
        (async () => {
            if (isPending) {
                const q = formData.search;
                setFormData({ search: '' });
                console.log(q)
               
                mutateAsync(q).then(async (response) => {
                    console.log(response)
                    if (response.ok) {
                        console.log("Got Response!")
                      const id = uuidv4();
                      setCurrentBotMessageId(id);
                      setIsPending(false);
                      setIsGettingDetails(true);
            
                      const reader = response.body.getReader();
                      setReader(reader);
                    }
                    else{
                        const id = uuidv4();
                        setCurrentBotMessageId(id);
                        setIsPending(false);
                        setIsGettingDetails(true);
    
                        setCurrentResponse({
                            Summary: "Sorry, there was an internal error while generating your response.",
                    Details: {},
                    OutOfContext: false,
                        });
                    }
                  });

                setFormData({ search: '' });
            }
        })();    
    // eslint-disable-next-line
    }, [isPending]);

    React.useEffect(() => {
        if (reader) {
            console.log("Got Reader")
          const handleStream = async () => {
            const botMessage = {
              id: currentBotMessageId,
              from: "bot",
              message: '',
              details: [],
              segmentLabels: [],
            };
    
            const decoder = new TextDecoder();
    
            let allChunks = '';
            const flag = true;
            while (flag) {
              const { done, value } = await reader.read();
              if (done) {
                setIsGettingDetails(false);
                setCurrentBotMessageId('');
                setReader(null);
                break;
              }
              const text = decoder.decode(value);
              allChunks = `${allChunks}${text}`;

              botMessage.message = getSummary(allChunks);
              botMessage.segmentLabels = getTitles(allChunks);
              botMessage.details = getDetails(allChunks);
              setChatContent([...chatContent, botMessage]);
              props.setMessages([
                  ...props.messages,
                  {
                  persona: botPersonaName,
                  message: botMessage.message,
                  details: botMessage.details,
                  segmentLabels: botMessage.segmentLabels,
                  outOfContext: false,
                  },
                ]);
    
              handleScrollTop();
            }
          };
    
          handleStream();
        }
        // eslint-disable-next-line
      }, [reader, currentBotMessageId]);

      React.useEffect(() => {
        // Stop consuming the stream when clicking Cancel Search
        if (stopLoop && reader) {
          reader.cancel();
          setStopLoop(false);
          setIsGettingDetails(false);
          setCurrentBotMessageId('');
          setReader(null);
        }
      }, [stopLoop, reader]);

    const handleChange = (e) => {
        e.preventDefault();
        setFormData({ ...formData, search: e.target.value });
      };

    React.useEffect(() => {
        if (currentResponse) {
            console.log(currentResponse)
            props.setMessages([
                ...props.messages,
                {
                persona: botPersonaName,
                message: currentResponse.Summary,
                details: currentResponse.Details,
                outOfContext: currentResponse.OutOfContext,
                },
            ]);


            setIsGettingDetails(false)
            setCurrentResponse(null)
        }
        // eslint-disable-next-line
      }, [currentResponse]);

    
      React.useEffect(() => {
        // Stop consuming the stream when clicking Cancel Search
        if (stopLoop && currentResponse) {
            currentResponse.cancel();
            setStopLoop(false);
            setIsGettingDetails(false);
            setCurrentBotMessageId('');
            setCurrentResponse(null);
        }
      }, [stopLoop, currentResponse]);

    const prefillReplayForm = (message, details) => {
        //add query param 
        console.log(details)
        navigate({
            pathname: "/addReplay",
            search: createSearchParams({
                program: props.searchContext.Program,
                event: props.searchContext.Name,
                description: message,
                details: details.sort((a,b) => {
                  const startDiff = a.Start - b.Start;
                  if (startDiff !== 0) {
                      return startDiff;
                  }

                  const endDiff = a.End - b.End;
                  return endDiff;

                }).reduce((res, detail)=>{
                    return res + `${detail.Start}, ${detail.End}\n`
                }, ""),
                replayMode: "SpecifiedTimestamps",
                audioTrack: 1,
                outputFormat: "Hls",
                resolutions: ["720p (1280 x 720)"]
            }).toString()
        },
    {
        replace: false
    })
    }

    return (
        <Grid item xs={props.size} style={{padding: "10px"}} className={classes.chatWindow} >
            <Grid item container direction="row" style={{justifyContent: "space-between", width: "95%" }}>
                <Typography variant="h2">Search</Typography>
                <IconButton size="small" onClick={props.onClose} >
                    <Tooltip title="Close Search">
                        <CloseIcon className={classes.iconSize}/>
                    </Tooltip>
                </IconButton>
            </Grid>
            <div ref={scrollableRef}>
            <Grid direction="column" className={classes.dialogue}>
                {
                    props.messages.map(correspondance => {
                        return(
                            <Grid item direction="column" className={`${correspondance.persona === userPersonaName ? classes.userPersona : classes.botPersona} ${classes.correspondance}` }>
                                <Typography variant="body1"><p>{correspondance.message && correspondance.message }</p></Typography>
                                {correspondance.segmentLabels && correspondance.segmentLabels.length > 0 && (
                                    <>
                                    <p>
                                      Segment title
                                      {correspondance.segmentLabels && correspondance.segmentLabels.length > 1
                                        ? `s`
                                        : ''}
                                      :
                                    </p>
                                    <ul>
                                      {correspondance.segmentLabels.map((label, index) => (
                                        <li key={label + index}>{label}</li>
                                      ))}
                                    </ul>
                                  </>
                                )}
                                { correspondance.details && correspondance.details.length > 0 && !isGettingDetails && <Button color="primary" onClick={() => prefillReplayForm(correspondance.message, correspondance.details)}>Generate Replay</Button>}
                            </Grid>
                        )
                        
                        })
                }
                  {(isPending || isGettingDetails)  && <CircularProgress size={20} style={{margin: "20px"}}/>}

            </Grid>
            </div>
            <Paper component="form" className={classes.root} onSubmit={handleSubmit} style={{margin: "-10px 10px"}}>
                    <Input
                        fullWidth
                        id="desc"
                        variant="outlined"
                        placeholder="Search within this event"
                        onChange={handleChange}
                        value={formData.search}
                        disabled={isPending || isGettingDetails}
                    />
                    <IconButton size="small" onClick={handleSubmit} >
                        <Tooltip title="Submit Prompt">
                            {isPending || isGettingDetails ? <CircularProgress size={20}/> : <ChevronRightIcon className={classes.iconSize}/>}
                            {/* {isPending || isGettingDetails ? <CircularProgress size={20}/> : <Icon><img src={GenAiSearchIcon}/></Icon>} */}
                        </Tooltip>
                    </IconButton>
                </Paper>
        </Grid>
    );
};