# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from MediaReplayEnginePluginHelper import OutputHelper
from MediaReplayEnginePluginHelper import Status
from MediaReplayEnginePluginHelper import DataPlane

score_range = [0,15,30,40,45]
game_range=[0,1,2,3,4,5,6,7]

def alpha_or_number(string):
    nalpha = 0
    nnumber = 0
    is_alp_num =0
    if not string:
        return '', 0
    for ch in string:
        if ch.isalpha(): nalpha+=1
        if ch.isnumeric(): nnumber +=1
    #array = string.strip().split(' ')
    if nalpha > nnumber * 2:
        is_alp_num = 1
        ret = string
    elif nnumber >= nalpha:
        is_alp_num = 2
        #array = string
        #print(string[-2:],string[-2:].isnumeric())
        if string[-2:].isnumeric() and int(string[-2:]) in score_range:
            score = string[-2:]
            array = string[:-2]
        elif string[-2:] == 'AD':
            score = 45
            array = string[:-2]
        else:
            score = ''
            array = string
        ret = []
        #print(array,type(score))
        for ch in array:
            print(ch)
            if not ch.isnumeric():
                continue
            ich = int(ch)
            if ich in score_range or ich in game_range:
                ret.append(ich)
            else:
                ret.extend([int(d) for d in str(ich)])
        if score: ret.append(int(score))
    else:
        ret = 'NAN'
    return ret, is_alp_num

#state = ['SENTINEL','RANK','NAME','SCORE','END']
#istate =     0       1      2       3      4

def analyze_score(score_list, debug):
    score_merge = ' '.join(score_list)
    score_items = score_merge.split(' ')
    score = {}
    score['Player'] = ''
    istate = 0
    print('Analyze score:',score_items,len(score_items))

    for idx in range(len(score_items)):
        if debug: print(idx,'--->',score_items[idx])
        item = score_items[idx]
        ret, is_alp_num = alpha_or_number(item)
        if debug: print(f'{ret} is alp_num {is_alp_num}, istate={istate}')
        if not is_alp_num: continue

        move = 1
        #Alphabetic item
        if is_alp_num == 1 :
            if istate == 0 :
                score['Player'] += ret
                move = 2
            elif istate == 1:
                score['Player'] += ret
            elif istate == 2:
                score['Player'] += ret
                move = 0
            elif istate == 3:
                if ret == 'AD':
                    score['Score'] = 45
                    move = 0
        #Numeric item
        elif is_alp_num == 2:
            if istate == 0:
                score['Player'] += str(ret)
            elif istate == 1:
                score['Player'] += str(ret)
                move = 0
            elif istate == 2:
                score['Game'] = ret
            elif istate == 3:
                score['Game'].extend(ret)
                move = 0
            else:
                return ret, False
        #Sth else
        else:
            move = 0
            continue

        ##########################
        istate += move
        ##########################
        if debug: print('istate after move',move,'step is',istate)
        if istate == 4:
            break

    else:
        if debug: print('Reached the end of for loop',istate)
        if istate < 3:
            return 'No score read at end of the loop',False

    if debug: print('score before clean',score)
    if 'Score' not in score.keys():
        if len(score['Game']) ==0:
            return 'No score and no game',False
        if score['Game'][-1] in score_range:
            score['Score'] = score['Game'][-1]
            # In case that there is no Game left
            if len(score['Game']) == 1:
                score['Game'][0] = 0
            else:
                score['Game'].pop()
        else:
            score['Score'] = 0

    if score['Score'] not in score_range:
        return 'Wrong scores',False

    games = [True if gm in game_range else False for gm in score['Game']]
    if all(games) == False:
        return 'Wrong games',False

    return score, True

def parse_score(score_array, debug):
    if debug: print('raw score is :',score_array)
    score1, sts1 = analyze_score(score_array[0], debug)
    score2, sts2 = analyze_score(score_array[1], debug)
    if all([sts1, sts2]):
        return [score1,score2]
    else:
        return []

def check_set_point(g1, g2, gp, bp, wgm):
    if gp and g1>=wgm-1 and g1 > g2:
        return True
    elif bp and g2>=wgm-1 and g2 > g1:
        return True
    else:
        return False

def check_match_point(gm1, gm2, g1_or_g2, wgm):
    if len(gm1) != len(gm2):
        return False
    wlist = [True if g1>g2 else False for (g1,g2) in zip(gm1,gm2)]
    w1 = wlist.count(True)
    w2 = wlist.count(False)
    #print(wlist,w1,w2)
    if g1_or_g2 and w1 == wgm-1:
        return True
    elif not g1_or_g2 and w2 == wgm-1:
        return True
    else:
        return False


def check_game_status(score, server):
    if server not in [0,1] or len(score) < 2:
        return 'False','False','False','False'
    receiver = 1 - server
    sevScore = score[server]['Score']
    recScore = score[receiver]['Score']
    gamePoint = False
    breakPoint = False
    setPoint = False
    matchPoint = False

    if sevScore >= 40 and recScore < sevScore:
        gamePoint = True
        breakPoint = False
    if sevScore < recScore and recScore >= 40:
        gamePoint = False
        breakPoint = True
    if any([gamePoint, breakPoint]):
        #print('Check if it is setPoint or matchPoint')
        if len(score[server]['Game']) == len(score[receiver]['Game']):
            g1 = score[server]['Game'][-1]
            g2 = score[receiver]['Game'][-1]
            #The first one to reach 6 games and win by 2 games wins
            #No tiebreaker
            setPoint = check_set_point(g1, g2, gamePoint, breakPoint, 6)
            if setPoint:
                s1 = score[server]['Game'][:-1]
                s2 = score[receiver]['Game'][:-1]
                #The first one to reach wgm games wins
                # wgm = 3 for 3 out of 5 format
                # wgm = 2 for 2 out of 3 format
                matchPoint = check_match_point(s1, s2, g1>g2, 2)
    return str(breakPoint), str(gamePoint), str(setPoint), str(matchPoint)

def most_frequent(List):
    if List:
        num = List[0]
    else:
        return [],0

    counter = 0
    for i in List:
        curr_frequency = List.count(i)
        if(curr_frequency> counter):
            counter = curr_frequency
            num = i
    return num, counter

def get_score_for_segments(segments, deppluginname):
    results = []
    result = {}

    for seg in segments:
        result['LabelCode'] = 'Not Attempted'
        result['Start'] = seg['Segment']['Start']
        result['End'] = seg['Segment']['End']
        raw_scores = [lb['Score'] for lb in seg['DependentPluginsOutput'][deppluginname]]
        raw_score, freq = most_frequent(raw_scores)
        if raw_score:
            #print(raw_score)
            result['rawScore'] = raw_score
            score = parse_score(raw_score, False)
            print(score)
            if score:
                result['Score'] = str(score)
            else:
                result['Score'] = 'NA'
        else:
            score = []
            result['rawScore'] = 'NA'
            result['Score'] = 'NA'
        if result['Score'] == 'NA':
            result['LabelCode'] = ''
        else:
            result['LabelCode'] = 'Score Detected;'

        servers = [lb['Server'] for lb in seg['DependentPluginsOutput'][deppluginname]]
        server, freq = most_frequent(servers)
        if server != []:
            print('Server is',server)
            result['Server'] = server
        else:
            result['Server'] = -1
        if result['Server'] != -1:
            result['LabelCode'] += 'Server Detected;'

        result['BreakPoint'],result['GamePoint'],result['SetPoint'],result['MatchPoint'] = check_game_status(score, server)
        result['Label'] = 'Score='+result['Score']

        results.append(result)

    return results

def lambda_handler(event, context):
    print (event)
    results = []
    mre_dataplane = DataPlane(event)

    # 'event' is the input event payload passed to Lambda
    mre_outputhelper = OutputHelper(event)
    pluginWithData = event['Plugin']['Configuration']['dependent_plugin_name']
    try:

        # plugin params
        jsonResults = mre_dataplane.get_segment_state_for_labeling()
        print('jsonResults=',jsonResults)
        results = get_score_for_segments(jsonResults, pluginWithData)
        print('results=',results)

        # Add the results of the plugin to the payload (required if the plugin status is "complete"; Optional if the plugin has any errors)
        mre_outputhelper.add_results_to_output(results)

        # Persist plugin results for later use
        mre_dataplane.save_plugin_results(results)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_COMPLETE)

        # Returns expected payload built by MRE helper library
        return mre_outputhelper.get_output_object()

    except Exception as e:
        print(e)

        # Update the processing status of the plugin (required)
        mre_outputhelper.update_plugin_status(Status.PLUGIN_ERROR)

        # Re-raise the exception to MRE processing where it will be handled
        raise
