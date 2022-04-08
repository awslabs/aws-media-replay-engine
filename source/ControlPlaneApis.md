# Original API Routes in Control Plane



@app.route('/version', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/uuid', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/system/configuration', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/system/configuration/{name}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/system/configuration/all', cors=True, methods=['GET'], authorizer=authorizer)
-----------------------------------------
@app.route('/plugin', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/plugin/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/plugin/class/{plugin_class}/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/plugin/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/plugin/class/{plugin_class}/contentgroup/{content_group}/all', cors=True, methods=['GET'],
@app.route('/plugin/{name}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/plugin/{name}/version/{version}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/plugin/{name}/version/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/plugin/{name}', cors=True, methods=['DELETE'], authorizer=authorizer)
@app.route('/plugin/{name}/version/{version}', cors=True, methods=['DELETE'], authorizer=authorizer)
@app.route('/plugin/{name}/status', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/plugin/{name}/version/{version}/status', cors=True, methods=['PUT'], authorizer=authorizer)
-----------------------------------------
@app.route('/profile', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/profile/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/profile/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/profile/{name}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/profile/{name}', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/profile/{name}/status', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/profile/{name}', cors=True, methods=['DELETE'], authorizer=authorizer)
-----------------------------------------
@app.route('/model', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/model/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/model/pluginclass/{plugin_class}/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/model/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/model/pluginclass/{plugin_class}/contentgroup/{content_group}/all', cors=True, methods=['GET'],
@app.route('/model/{name}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/model/{name}/version/{version}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/model/{name}/version/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/model/{name}/status', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/model/{name}/version/{version}/status', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/model/{name}', cors=True, methods=['DELETE'], authorizer=authorizer)
@app.route('/model/{name}/version/{version}', cors=True, methods=['DELETE'], authorizer=authorizer)
-----------------------------------------
@app.route('/event', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/event/contentgroup/{content_group}/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/event/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/event/{name}/program/{program}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/event/{name}/program/{program}', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/event/{name}/program/{program}', cors=True, methods=['DELETE'], authorizer=authorizer)
@app.route('/event/{name}/program/{program}/timecode/firstpts/{first_pts}', cors=True, methods=['PUT'],
@app.route('/event/{name}/program/{program}/timecode/firstpts', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/event/{name}/program/{program}/framerate/{frame_rate}', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/event/metadata/track/audio', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/event/{name}/program/{program}/status/{status}', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/event/{name}/program/{program}/status', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/event/all/external', cors=True, methods=['GET'], authorizer=jwt_auth)
@app.route('/event/future/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/event/range/{fromDate}/{toDate}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/event/queued/all/limit/{limit}/closestEventFirst/{closestEventFirst}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/event/processed/{id}', cors=True, methods=['DELETE'], authorizer=authorizer)
@app.route('/event/program/hlslocation/update', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/event/program/edllocation/update', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/event/{name}/program/{program}/hasreplays', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/event/program/export_data', cors=True, methods=['PUT'],
@app.route('/export/data/event/{event}/program/{program}', cors=True, methods=['GET'],
@app.route('/program/{program}/event/{event}/edl/track/{audiotrack}', cors=True, methods=['GET'], 
@app.route('/program/{program}/event/{event}/hls/eventmanifest/track/{audiotrack}', cors=True, methods=['GET'],

-----------------------------------------

@app.route('/contentgroup/{content_group}', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/contentgroup/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/contentgroup/{content_group}', cors=True, methods=['DELETE'], authorizer=authorizer)
-----------------------------------------
@app.route('/program/{program}', cors=True, methods=['PUT'], authorizer=authorizer)
@app.route('/program/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/program/{program}', cors=True, methods=['DELETE'], authorizer=authorizer)



-----------------------------------------

@app.route('/workflow/execution', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status/{status}',
@app.route('/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status',
@app.route('/workflow/execution/program/{program}/event/{event}/chunk/{chunk_num}/plugin/{plugin_name}/status/incomplete',

-----------------------------------------

@app.route('/replay', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/replay/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/replay/program/{program}/event/{event}/all', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/replay/all/contentgroup/{contentGrp}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/replay/program/{program}/event/{event}/replayid/{id}', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/replay/program/{program}/event/{event}/replayid/{id}/status/update/{replaystatus}', cors=True,
@app.route('/replayrequests/completed/events/track/{audioTrack}/program/{program}/event/{event}', cors=True,
@app.route('/replayrequests/track/{audioTrack}/program/{program}/event/{event}', cors=True, methods=['GET'],
@app.route('/replayrequests/program/{program}/event/{event}/segmentend', cors=True, methods=['GET'],
@app.route('/replay/program/{program}/event/{event}/features', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/replayrequest/mp4location/update', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/replayrequest/update/hls/manifest', cors=True, methods=['POST'], authorizer=authorizer)
@app.route('/replay/event/{name}/program/{program}/id/{replayid}', cors=True, methods=['DELETE'], authorizer=authorizer)
@app.route('/replay/event/program/export_data', cors=True, methods=['PUT'],authorizer=authorizer)
@app.route('/export/data/replay/{id}/event/{event}/program/{program}', cors=True, methods=['GET'],
@app.route('/program/{program}/gameid/{event}/hls/stream/locations', cors=True, methods=['GET'], 
@app.route('/mre/streaming/auth', cors=True, methods=['GET'], authorizer=jwt_auth)
@app.route('/program/{program}/event/{event}/hls/replaymanifest/replayid/{replayid}', cors=True, methods=['GET'],

-----------------------------------------
@app.route('/medialive/channels', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/mediatailor/channels', cors=True, methods=['GET'], authorizer=authorizer)
@app.route('/mediatailor/playbackconfigurations', cors=True, methods=['GET'], authorizer=authorizer)


-----------------------------------------




