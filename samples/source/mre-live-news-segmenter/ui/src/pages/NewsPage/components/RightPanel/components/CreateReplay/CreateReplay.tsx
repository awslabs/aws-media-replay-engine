import { Badge, Button, Flex } from '@aws-amplify/ui-react';
import { TextAreaField, TextField } from '@aws-amplify/ui-react';
import { Radio, RadioGroupField } from '@aws-amplify/ui-react';
import { CheckboxField } from '@aws-amplify/ui-react';
import { SelectField } from '@aws-amplify/ui-react';
import { Card } from '@aws-amplify/ui-react';
import { Input, Label } from '@aws-amplify/ui-react';
import { SliderField } from '@aws-amplify/ui-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from '@aws-amplify/ui-react';
import { ChangeEvent, useEffect, useState } from 'react';
import { Dict } from 'styled-components/dist/types';

import { BaseButton, BaseModal } from '@src/components';
import { useNewsPageContext } from '@src/contexts';
import { services } from '@src/services';
import {
  BaseFunction,
  DurationBasedClip,
  FeatureBasedClip,
  ReplayRequest,
  TimeBasedClip,
} from '@src/types';

interface CreateReplayProps {
  visible: boolean;
  onClose: BaseFunction;
  program: string;
  event: string;
  user: string;
  description: string;
  specifiedTimestamps?: string;
  replayMode?: string;
}

export const CreateReplay = (props: CreateReplayProps) => {
  const [selectedProgram] = useState(props.program);
  const [selectedTransition, setSelectedTransition] = useState('None');
  const [selectedTransitionConfig, setSelectedTransitionConfig] = useState('');
  const [selectedEvent] = useState(props.event);
  const [selectedAudioTrack] = useState(1);
  const [replayDescription, setReplayDescription] = useState(props.description);
  const [replayMode] = useState(props.replayMode);
  const [replayDuration] = useState(60);
  const [specifiedTimestamps, setSpecifiedTimetamps] = useState(
    props.specifiedTimestamps ?? '',
  );
  const [formInvalid, setFormInvalid] = useState(true);
  const [featuresObject] = useState<Dict>([]);
  const [pluginNamePlusAttribValues] = useState(
    [],
  );
  const [resolutionValues, setResolutionValues] = useState<string[]>([
    '720p (1280 x 720)',
  ]);
  const [selectedResolution, setSelectedResolution] =
    useState('720p (1280 x 720)');
  const [outputFormat, setOutputFormat] = useState('Mp4');
  const [uxlabel, setUXlabel] = useState(`${props.program} | ${props.event}`);
  const [fadeInMs] = useState(500);
  const [fadeOutMs] = useState(500);
  const [durationFromToleranceValue] =
    useState(30);
  const [checkBoxState, setCheckBoxState] = useState({
    checkedFillToExact: true,
    checkedEqualDistro: false,
    checkedCatchup: false,
    checkedTransitions: true,
    checkedIgnoreLowQualitySegments: false,
    checkedIncludeHighQualitySegments: false,
  });

  const { setReplayRequest } = useNewsPageContext();

  const handleCheckBoxChange = (e: ChangeEvent<HTMLInputElement>) => {
    setCheckBoxState({ ...checkBoxState, [e.target.name]: e.target.checked });
  };

  const Resolutions = [
    '4K (3840 x 2160)',
    '2K (2560 x 1440)',
    '16:9 (1920 x 1080)',
    '1:1 (1080 x 1080)',
    '4:5 (864 x 1080)',
    '9:16 (608 x 1080)',
    '720p (1280 x 720)',
    '480p (854 x 480)',
    '360p (640 x 360)',
  ];

  const isTimestampsValid = (ts: string) => {
    // Using a regular expression to check if the input is a comma delimited list of non-negative floats
    // each pair being on a new line
    // Does NOT compare the values in the list
    const re =
      /^\s*\d+(\.\d+)?\s*,\s*\d+(\.\d+)?\s*(\r?\n\s*\d+(\.\d+)?\s*,\s*\d+(\.\d+)?\s*)*$/g;
    return re.test(ts);
  };

  useEffect(() => {
    //console.log(replayMode);
    if (replayDescription.trim() === '' || uxlabel.trim() === '')
      setFormInvalid(true);
    else {
      if (outputFormat !== '') {
        if (resolutionValues.length === 0) {
          setFormInvalid(true);
          return;
        }
      }

      if (replayMode === 'SpecifiedTimestamps') {
        if (!isTimestampsValid(specifiedTimestamps)) {
          setFormInvalid(true);
        } else setFormInvalid(false);
      } else setFormInvalid(false);
    }
  }, [
    selectedProgram,
    selectedEvent,
    selectedAudioTrack,
    replayDescription,
    featuresObject,
    replayMode,
    resolutionValues,
    outputFormat,
    uxlabel,
    specifiedTimestamps,
  ]);

  const getFormValues = () => {
    let formValues: ReplayRequest = {
      Program: selectedProgram,
      Event: selectedEvent,
      AudioTrack: 1,
      Description: replayDescription,
      UxLabel: uxlabel,
      Requester: props.user,
      Catchup: checkBoxState.checkedCatchup,
      CreateMp4: outputFormat === 'Mp4' ? true : false,
      CreateHls: outputFormat === 'Hls' ? true : false,
      ClipfeaturebasedSummarization: replayMode === 'Clips' ? true : false,
      Resolutions: outputFormat !== '' ? resolutionValues : [],
      IgnoreDislikedSegments: checkBoxState.checkedIgnoreLowQualitySegments,
      IncludeLikedSegments: checkBoxState.checkedIncludeHighQualitySegments,
      TransitionName: '',
      TransitionOverride: {
        FadeInMs: 500,
        FadeOutMs: 500,
      },
      Priorities: {
        Clips: [],
      },
      SpecifiedTimestamps: '',
      DurationbasedSummarization: undefined,
    };
    if (replayMode === 'Duration') {
      formValues['DurationbasedSummarization'] = {
        Duration: replayDuration,
        FillToExact: checkBoxState.checkedFillToExact,
        EqualDistribution: checkBoxState.checkedEqualDistro,
        ToleranceMaxLimitInSecs: durationFromToleranceValue,
      };
    }
    if (replayMode === 'SpecifiedTimestamps') {
      formValues['SpecifiedTimestamps'] = specifiedTimestamps;
    }

    // Get Priority Info
    let clips: (TimeBasedClip | FeatureBasedClip | DurationBasedClip)[] = [];
    if (replayMode === 'SpecifiedTimestamps') {
      //split specifiedtimestamps by new line character
      let timestampsPairs = specifiedTimestamps.split('\n');
      timestampsPairs.forEach((pair: string) => {
        //split the pair by comma
        //confirm that a comma was found
        if (pair.indexOf(',') !== -1) {
          let startTime = pair.split(',')[0];
          let endTime = pair.split(',')[1];
          let clip: TimeBasedClip = {
            StartTime: parseFloat(startTime),
            EndTime: parseFloat(endTime),
            Name: startTime + ' - ' + endTime,
          };
          //validate that name start time and end time are all not null
          clips.push(clip);
        }
      });
    } else {
      featuresObject.forEach((f: Dict) => {
        if (replayMode === 'Duration') {
          let clipinfo = f[Object.keys(f)[0]].split('^');

          // Consider features whose Weight is more than Zero , which means they are included in the replay
          if (parseInt(clipinfo[0]) > 0) {
            let clip: DurationBasedClip = {
              Name: Object.keys(f)[0],
              Weight: parseInt(clipinfo[0]),
              AttribName: clipinfo[4].trim(),
              AttribValue: clipinfo[3].trim() === 'false' ? false : true,
              PluginName: clipinfo[5].trim(),
            };
            clips.push(clip);
          }
        }

        if (replayMode === 'Clips') {
          let clipinfo = f[Object.keys(f)[0]].split('^');
          let clip: FeatureBasedClip = {
            Name: Object.keys(f)[0],
            Include: clipinfo[1] == 'true' ? true : false,
            AttribValue: clipinfo[3].trim() === 'false' ? false : true,
            AttribName: clipinfo[4].trim(),
            PluginName: clipinfo[5].trim(),
          };
          //console.log('clipinfo: ', clipinfo);

          clip['Name'] = Object.keys(f)[0];
          clip['Include'] = clipinfo[1] == 'true' ? true : false;
          // Include all Plugins
          pluginNamePlusAttribValues.forEach((feature: string) => {
            const featureValues = feature.split('|');
            if (feature === Object.keys(f)[0]) {
              let clip: FeatureBasedClip = {
                Name: Object.keys(f)[0],
                Include: clipinfo[1] == 'true' ? true : false,
                AttribValue: featureValues[2].trim() === 'false' ? false : true,
                AttribName: featureValues[1].trim(),
                PluginName: featureValues[0].trim(),
              };
              clips.push(clip);
            }
          });
        }
      });
    }
    formValues['Priorities'] = {
      Clips: clips,
    };
    formValues['TransitionName'] = selectedTransition;

    // Non Image Transitions may not have Config
    if (selectedTransitionConfig.hasOwnProperty('Config')) {
      formValues['TransitionOverride'] = {
        FadeInMs: fadeInMs,
        FadeOutMs: fadeOutMs,
      };
    }

    return formValues;
  };

  const handleFormSubmit = async () => {
    const replayRequest = getFormValues();
    if (!formInvalid) {
      try {
        services.postReplay(replayRequest);
      } catch (error) {
        console.log(error);
        return { success: false };
      } finally {
        props.onClose();
        setReplayRequest(replayRequest);
      }
    }
  };

  const handleClose = () => {
    props.onClose();
  };

  return (
    <BaseModal
      visible={props.visible}
      onClose={handleClose}
      header="Create Replay"
      content={
        <>
          <TextAreaField
            placeholder="Describe the contents of the replay here."
            label="Description"
            errorMessage="Description must be included in replay"
            hasError={!replayDescription}
            marginTop={40}
            rows={7}
            value={replayDescription}
            onChange={(e) => setReplayDescription(e.target.value)}
          />
          <TextField
            placeholder="Replay Label"
            label="Label"
            errorMessage="There is an error"
            marginTop={20}
            value={uxlabel}
            onChange={(e) => setUXlabel(e.target.value)}
          />
          {replayMode !== 'SpecifiedTimestamps' && (
            <>
              <CheckboxField
                label="Ignore manually deselected segments?"
                marginTop={20}
                checked={checkBoxState.checkedIgnoreLowQualitySegments}
                onChange={handleCheckBoxChange}
                name="checkedIgnoreLowQualitySegments"
              />
              <CheckboxField
                label="Include manually selected segments?"
                checked={checkBoxState.checkedIncludeHighQualitySegments}
                onChange={handleCheckBoxChange}
                name="checkedIncludeHighQualitySegments"
              />
            </>
          )}
          {/* <RadioGroupField
            legend="Replay Mode"
            name="replayMode"
            marginTop={20}
            value={replayMode}
            onChange={(e) => setReplayMode(e.target.value)}
        >
            <Radio value="Duration">Duration Based (Secs)</Radio>
            <Radio value="SpecifiedTimestamps">Specified Timestamps</Radio>
            <Radio value="Clips">Clip Feature Based</Radio>
        </RadioGroupField> */}
          {replayMode === 'SpecifiedTimestamps' && (
            <TextAreaField
              placeholder="0.0,60.0 &#10;90.0,120.0&#10;131.32,140.5"
              label="Specified Timestamps"
              errorMessage="​Must be a comma delimited list of non-negative floating point values"
              hasError={!isTimestampsValid(specifiedTimestamps)}
              marginTop={40}
              rows={5}
              value={specifiedTimestamps}
              onChange={(e) => setSpecifiedTimetamps(e.target.value)}
            />
          )}
          {replayMode === 'Duration' && (
            <Card variation="outlined" marginTop={20}>
              <Flex direction="row" gap="medium">
                <Flex direction="column" gap="small">
                  <Label htmlFor="quantity">Target Reel Duration (Secs) </Label>
                  <Input id="quantity" type="number" />
                </Flex>
                <SliderField
                  label="Tolerance (Secs)"
                  min={0}
                  max={60}
                  step={1}
                  defaultValue={30}
                />
                <CheckboxField
                  label="Equal Distribution?"
                  checked={checkBoxState.checkedEqualDistro}
                  onChange={handleCheckBoxChange}
                  name="checkedEqualDistro"
                />
              </Flex>
            </Card>
          )}
          {replayMode !== 'SpecifiedTimestamps' && (
            <Card
              variation="outlined"
              marginTop={20}
              height={300}
              style={{ overflowY: 'auto' }}
            >
              <h3>Priorities</h3>
              <Table caption="" highlightOnHover={false}>
                <TableHead>
                  <TableRow>
                    <TableCell as="th">Feature Plugin</TableCell>
                    <TableCell as="th">
                      {replayMode === 'Duration'
                        ? 'Weight (1-100, 0-Exclude)'
                        : 'Include?'}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell>Feature Name</TableCell>
                    <TableCell>
                      {replayMode === 'Duration' ? (
                        <Input id="quantity" type="number" min={0} max={100} />
                      ) : (
                        <CheckboxField
                          label="include?"
                          labelHidden={true}
                          name="include?"
                          value="yes"
                          marginTop={20}
                        />
                      )}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </Card>
          )}
          {replayMode !== 'SpecifiedTimestamps' && (
            <CheckboxField
              label="catchUp"
              checked={checkBoxState.checkedCatchup}
              onChange={handleCheckBoxChange}
              name="checkedCatchup"
              marginTop={20}
            />
          )}
          <RadioGroupField
            legend="Output Format"
            name="outputFormat"
            value={outputFormat}
            onChange={(e) => {
              setOutputFormat(e.target.value);
              if (e.target.value === "Hls") {
                setResolutionValues(resolutionValues.length > 0 ? [selectedResolution] : []);
              }
            }}
            marginTop={20}
          >
            <Radio value="Hls">Create HLS Program</Radio>
            <Radio value="Mp4">Create MP4 Program</Radio>
          </RadioGroupField>
          {outputFormat && (
            <>
              <SelectField
                label={outputFormat === "Hls" ? "Output Resolution" : "Output Resolutions"}
                marginTop={20}
                style={{ background: 'none' }}
                value={selectedResolution}
                onChange={(e) => {
                  setSelectedResolution(e.target.value);
                  if (outputFormat === "Hls"){
                    setResolutionValues([e.target.value])
                  }
                  else if (outputFormat === "Mp4") {
                    setResolutionValues(
                      Array.from(
                        new Set([...resolutionValues, e.target.value]),
                      ),
                    );
                  }
                }}
              >
                {Resolutions.map((r, index) => {
                  return (
                    <option key={index} style={{ color: '#000' }} value={r}>
                      {r}
                    </option>
                  );
                })}
              </SelectField>
              {resolutionValues.map((resolution, index) => (
                //return a badge containing the resolution, as well as n x mark that removes the resolution
                <Badge
                  marginTop={10}
                  key={index}
                  style={{ margin: '5px', color: '#000' }}
                >
                  {resolution} &emsp;
                  <span
                    style={{ cursor: 'pointer' }}
                    onClick={() => {
                      const newSet = resolutionValues.filter(
                        (item) => item !== resolution,
                      );
                      setResolutionValues(newSet);
                      setSelectedResolution(newSet[0]);
                    }}
                  >
                    x
                  </span>
                </Badge>
              ))}
            </>
          )}
          <SelectField
            label="Video Transition Effects"
            marginTop={20}
            style={{ background: 'none' }}
            value={selectedTransition}
            onChange={(e) => {
              setSelectedTransition(e.target.value);
              setSelectedTransitionConfig(e.target.value);
            }}
          >
            <option value="FadeInFadeOut">FadeInFadeOut</option>
            <option value="None">None</option>
          </SelectField>
        </>
      }
      footer={
        <>
          <Button onClick={handleClose} variation="link">
            Cancel
          </Button>
          <BaseButton
            disabled={formInvalid}
            onClick={() => handleFormSubmit()}
            variation="primary"
          >
            Submit
          </BaseButton>
        </>
      }
      width={700}
    />
  );
};
