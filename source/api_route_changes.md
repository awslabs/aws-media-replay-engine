# Log all API route changes here

## ControlPlane APIs
-----------------------------
## Replay API


1. GET

```python
/export/data/replay/{id}/event/{event}/program/{program}
```
To
```python
/replay/export/data/{id}/event/{event}/program/{program}
```


2. 

```python
/program/{program}/gameid/{event}/hls/stream/locations
```

to
```python
/replay/program/{program}/gameid/{event}/hls/stream/locations
```

3. 

```python
/mre/streaming/auth
```

to
```python
/replay/mre/streaming/auth
```

4.
```python
/replayrequest/update/hls/manifest
```
to
```python
/replay/update/hls/manifest
```
5.
```python
/replayrequest/mp4location/update
```
to

```python
/replay/mp4location/update
```

6. 
```python
/program/{program}/event/{event}/hls/replaymanifest/replayid/{replayid}
```
to 
```python
/replay/program/{program}/event/{event}/hls/replaymanifest/replayid/{replayid}
```
7. 
```python
/replayrequests/program/{program}/event/{event}/segmentend
```
to 
```python
/replay/program/{program}/event/{event}/segmentend
```
8.
```python
/replayrequests/track/{audioTrack}/program/{program}/event/{event}
```
to 
```python
/replay/track/{audioTrack}/program/{program}/event/{event}
```
9. 
```python
/replayrequests/completed/events/track/{audioTrack}/program/{program}/event/{event}
```
to
```python
/replay/completed/events/track/{audioTrack}/program/{program}/event/{event}
```
10. 










---------------------------------------------------------------------------------------------------

## Event API

1. GET

```python
/export/data/event/{event}/program/{program}
```

to

```python
/event/{name}/export/data/program/{program}
```
2.

/program/{program}/event/{event}/edl/track/{audiotrack}

to


/event/{name}/edl/track/{audiotrack}/program/{program}

3


/program/{program}/event/{event}/hls/eventmanifest/track/{audiotrack}


to 

/event/{name}/hls/eventmanifest/track/{audiotrack}/program/{program}

4. 
Add these into Event API

/export/data/event/{event}/program/{program} - CHANGED
/program/{program}/event/{event}/edl/track/{audiotrack} - CHANGED
/program/{program}/event/{event}/hls/eventmanifest/track/{audiotrack} - CHANGED

/event/processed/{id}
/event/program/export_data
/event/{name}/program/{program}/hasreplays
/event/queued/all/limit/{limit}/closestEventFirst/{closestEventFirst}
/event/range/{fromDate}/{toDate}
/event/future/all
/event/all/external
/event/program/edllocation/update
/event/program/hlslocation/update

---------------------------------------------------------------------------------------------------------

## System API

### Add the following into System API

1. 

/medialive/channels

to 

/system/medialive/channels'

2.

/mediatailor/channels

to

/system/mediatailor/channels

3.

/mediatailor/playbackconfigurations

to

/system/mediatailor/playbackconfigurations

4.

/version

to 

/system/version

5.

/uuid

to 

/system/uuid

6. /system/configuration
7. /system/configuration/{name}
8. /system/configuration/all
