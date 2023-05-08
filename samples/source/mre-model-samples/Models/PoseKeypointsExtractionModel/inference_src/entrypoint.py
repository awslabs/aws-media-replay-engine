# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

## import packages ##
import base64
import json
import mxnet as mx
from mxnet import gpu
import numpy as np
from mxnet import nd, image
import sys
import gluoncv as gcv
from gluoncv import data as gdata
from gluoncv.data.transforms.pose import detector_to_simple_pose, heatmap_to_coord, get_max_pred

## SageMaker loading function ##
YOLO3_MODEL = 'yolo3_mobilenet1.0_coco'
#POSE_MODEL = 'simple_pose_resnet101_v1d'
POSE_MODEL = 'simple_pose_resnet18_v1b'

def model_fn(model_dir):
    """
    Load the pretrained model 
    
    Args:
        model_dir (str): directory where model artifacts are saved/loaded
    """
    print('Ready to load model from '+model_dir)
    model_yolo = gcv.model_zoo.get_model(YOLO3_MODEL,  pretrained_base=False)
    model_pose = gcv.model_zoo.get_model(POSE_MODEL,  pretrained_base=False)
    ctx = mx.cpu(0)
    
    model_yolo.load_parameters(f'{model_dir}/{YOLO3_MODEL}-66dbbae6.params', ctx, ignore_extra=True)
    print('Gluoncv YOLO model loaded')
    model_pose.load_parameters(f'{model_dir}/{POSE_MODEL}-f63d42ac.params', ctx, ignore_extra=True)
    print('Gluoncv SimplePose model loaded')
    
    model_yolo.reset_class(["person"], reuse_weights=['person'])
    return model_yolo, model_pose, ctx


def heatmap_to_coord_ratio(heatmaps, bbox_list):
    # The heatmap is for each bbox
    heatmap_height = heatmaps.shape[2]
    heatmap_width = heatmaps.shape[3]
    #coords: keypoints x/y coord to the heatmap
    #maxvals: confidence for each keypoints
    coords, maxvals = get_max_pred(heatmaps)
    #preds will record keypoints x/y coord to the whole image
    preds = nd.zeros_like(coords)
    #pred_ratio will record keypoints x/y coord ratio the the bbox
    preds_ratio = nd.zeros_like(coords)

    for i, bbox in enumerate(bbox_list):
        x0 = bbox[0]
        y0 = bbox[1]
        x1 = bbox[2]
        y1 = bbox[3]
        w = (x1 - x0) / 2
        h = (y1 - y0) / 2
        center = np.array([x0 + w, y0 + h])
        scale = np.array([w, h])

        w_ratio = coords[i][:, 0] / heatmap_width
        h_ratio = coords[i][:, 1] / heatmap_height
        preds[i][:, 0] = scale[0] * 2 * w_ratio + center[0] - scale[0]
        preds[i][:, 1] = scale[1] * 2 * h_ratio + center[1] - scale[1]
        preds_ratio[i][:, 0] = w_ratio
        preds_ratio[i][:, 1] = h_ratio
    return preds, preds_ratio, maxvals

## SageMaker inference function ##
def transform_fn(net, data, input_content_type, output_content_type):

    ## retrive model and contxt from the first parameter, net
    model_yolo, model_pose, ctx = net
    
    ## decode image ##
    # for endpoint API calls
    if type(data) == str:
        parsed = json.loads(data)
        img = mx.nd.array(parsed)
    # for batch transform jobs
    else:
        img = mx.img.imdecode(data)
        
    print('Original image size',img.shape)
    ## preprocess ##
    
    # normalization values taken from gluoncv
    # https://gluon-cv.mxnet.io/_modules/gluoncv/data/transforms/presets/rcnn.html
    mean = (0.485, 0.456, 0.406)
    std = (0.229, 0.224, 0.225)
    IMG_W = 800
    IMG_H = 600
    img = gdata.transforms.image.imresize(img, IMG_W, IMG_H)
    print('Resized image size',img.shape)
    imgr = mx.nd.image.to_tensor(img)
    imgr = mx.nd.image.normalize(imgr, mean=mean, std=std)
    nda = imgr.expand_dims(0)  
    nda = nda.copyto(ctx)
    
    
    ## inference ##
    cid, score, bbox = model_yolo(nda)
    #upscale_bbox by 1.25 to make sure human is all included
    pose_input, upscale_bbox = detector_to_simple_pose(img, cid, score, bbox)
    result = []
    qcresult = []
    if pose_input is None:
        return [{'prediction':result},{'qcresult':qcresult}]
    
    # Detect pose and generate heatmap
    predicted_heatmap = model_pose(pose_input)
    pred_coords, pred_ratio, confidence = heatmap_to_coord_ratio(predicted_heatmap, upscale_bbox)
    
    coords_list = pred_coords.asnumpy().tolist()
    ratio_list = pred_ratio.asnumpy().tolist()
    scores_list = score.asnumpy().tolist()

    for idx, ratio in enumerate(ratio_list):
        res = []
        qc = []
        res.append(scores_list[0][idx])
        qc.append(scores_list[0][idx])
        coords = coords_list[idx]
        for i, xy in enumerate(ratio):
            res.append([xy[0],xy[1]])
            qc.append([float(coords[i][0]/IMG_W),float(coords[i][1]/IMG_H)])
        result.append(res)
        qcresult.append(qc)

    predictionslist = [{'prediction':result}, {'qcresult':qcresult}]
    return predictionslist
