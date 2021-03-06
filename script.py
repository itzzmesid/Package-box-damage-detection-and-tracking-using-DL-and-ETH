# -*- coding: utf-8 -*-
"""Untitled2.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/10iNIkioEZLsTWPIacyqEGK4mxPNERzqU
"""


""""""


#Importing all necessary Libraries
import os
import sys
import json
import datetime
import numpy as np
import skimage.draw
import cv2
import pandas as pd
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from os import listdir
from xml.etree import ElementTree
from numpy import zeros,asarray,expand_dims,mean
from mrcnn.config import Config
from mrcnn import visualize
from mrcnn.visualize import display_instances
from mrcnn import model as modellib, utils
from mrcnn.utils import Dataset,compute_ap, compute_recall,compute_iou
from mrcnn.model import load_image_gt,mold_image, MaskRCNN
import zipfile

# Root directory of the project
ROOT_DIR = "C:\\Games\\Project"
COCO_WEIGHTS_PATH = os.path.join(ROOT_DIR, "C:\\Games\\Project\\mask_rcnn_coco.h5")
DEFAULT_LOGS_DIR = os.path.join(ROOT_DIR, "C:\\Games\\Project\\logs")

class CustomConfig(Config):
    # Give the configuration a recognizable name
    NAME = "name"
    IMAGES_PER_GPU = 1
    # Number of classes (including background)
    NUM_CLASSES = 2 + 1  # Background + damage + cardboard
    STEPS_PER_EPOCH = 100 # Number of training steps per epoch
    DETECTION_MIN_CONFIDENCE = 0.9  # Skip detections with < 90% confidence

class CustomDataset(utils.Dataset):
  def load_custom(self, dataset_dir, subset):
        # Add classes, we have two classes.
        self.add_class("name", 1, "cardboard")
        self.add_class("name", 2, "damage")

        # Train or validation dataset?
        assert subset in ["C:\\Games\\Project\\images\\box-train", "C:\\Games\\Project\\images\\box-valid"]
        dataset_dir = os.path.join(dataset_dir, subset)
        annotations1 = json.load(open(os.path.join(dataset_dir, "via_region_data.json")))
        annotations = list(annotations1.values())
        annotations = [a for a in annotations if a['regions']]
        for a in annotations:
            polygons = [r['shape_attributes'] for r in a['regions'].values()]
            objects = [s['region_attributes']['name'] for s in a['regions'].values()]
            name_dict = {"cardboard": 1,"damage": 2}
            num_ids = [name_dict[a] for a in objects]
            image_path = os.path.join(dataset_dir, a['filename'])
            image = skimage.io.imread(image_path)
            height, width = image.shape[:2]
            self.add_image(
                "name", 
                image_id=a['filename'],
                path=image_path,
                width=width, height=height,
                polygons=polygons,
                num_ids=num_ids)
  def load_mask(self, image_id):
        image_info = self.image_info[image_id]
        if image_info["source"] != "name":
            return super(self.__class__, self).load_mask(image_id)

        info = self.image_info[image_id]
        if info["source"] != "name":
            return super(self.__class__, self).load_mask(image_id)
        num_ids = info['num_ids']
        mask = np.zeros([info["height"], info["width"], len(info["polygons"])],
                        dtype=np.uint8)

        for i, p in enumerate(info["polygons"]):
          if p['name'] == 'polygon':
            rr, cc = skimage.draw.polygon(p['all_points_y'], p['all_points_x'])            
          elif p['name'] == 'rect':
            rr, cc = skimage.draw.rectangle(start=(p['x'], p['y']), end=(p['width'],p['height']))
          rr[rr > mask.shape[0]-1] = mask.shape[0]-1
          cc[cc > mask.shape[1]-1] = mask.shape[1]-1
          mask[rr, cc, i] = 1

        num_ids = np.array(num_ids, dtype=np.int32)
        return mask, num_ids

  def image_reference(self, image_id):
        """Return the path of the image."""
        info = self.image_info[image_id]
        if info["source"] == "name":
            return info["path"]
        else:
            super(self.__class__, self).image_reference(image_id)


config = CustomConfig()
model = modellib.MaskRCNN(mode="training", config=config,model_dir=DEFAULT_LOGS_DIR)

weights_path =COCO_WEIGHTS_PATH

if not os.path.exists(weights_path):
  utils.download_trained_weights(weights_path)

model.load_weights(weights_path, by_name=True, exclude=["mrcnn_class_logits", "mrcnn_bbox_fc","mrcnn_bbox", "mrcnn_mask"])



# Commented out IPython magic to ensure Python compatibility.
# %reload_ext tensorboard
# %tensorboard --logdir "/content/drive/My Drive/logs/"

config = CustomConfig()
class PredictionConfig(config.__class__):
  GPU_COUNT = 1
  IMAGES_PER_GPU = 1
  DETECTION_MIN_CONFIDENCE = 0.7

def get_ax(rows=1, cols=1, size=16):
   _, ax = plt.subplots(rows, cols, figsize=(size*cols, size*rows))
   return ax

def evaluate_model(dataset, model, cfg):
  APs = list()
  F1_scores = list()
  ARs=list()
  iou=list()
  for image_id in dataset.image_ids:
    image, image_meta, gt_class_id, gt_bbox, gt_mask = modellib.load_image_gt(dataset, cfg, image_id, use_mini_mask=False)
    yhat = model.detect([image], verbose=1)
    r = yhat[0]
    # Areas of anchors and GT boxes
    area1 = (r["rois"][:, 2] - r["rois"][:, 0]) * (r["rois"][:, 3] - r["rois"][:, 1])
    area2 = (gt_bbox[:, 2] - gt_bbox[:, 0]) * (gt_bbox[:, 3] - gt_bbox[:, 1])
    # Compute overlaps to generate matrix [r["rois"] count, gt_bbox count]
    # Each cell contains the IoU value.
    overlaps = np.zeros((r["rois"].shape[0], gt_bbox.shape[0]))
    for i in range(overlaps.shape[1]):
        box2 = gt_bbox[i]
        overlaps[:, i] = compute_iou(box2, r["rois"], area2[i], area1)
    iou.append(mean(overlaps))
    AP, precisions, recalls, overlaps = compute_ap(gt_bbox, gt_class_id, gt_mask, r["rois"], r["class_ids"], r["scores"], r['masks'])
    AR, positive_ids = compute_recall(r["rois"], gt_bbox, iou=0.2)
    ARs.append(AR)
    F1_scores.append((2* ((mean(precisions) * mean(recalls))/(mean(precisions) + mean(recalls)))))
    APs.append(AP)
  #Storing the values pf precision, Recall and F1 score in a .csv file
  data={"Image ID":dataset.image_ids,"Precision":APs,"Recall":ARs,"F1 score": F1_scores,"IoU":iou}
  df = pd.DataFrame(data)
  df.to_csv('Data.csv', index=False)
  mAP = mean(APs)
  mAR = mean(ARs)

#To test the data for validation

MODEL_DIR = os.path.join(ROOT_DIR,"logs")
test_set =CustomDataset()
test_set.load_custom(ROOT_DIR,"C:\\Games\\Project\\images\\box-valid")
test_set.prepare()

cfg = PredictionConfig()
model = modellib.MaskRCNN(mode="inference", model_dir=MODEL_DIR, config=cfg)
model.load_weights("C:\\Games\\Project\\logs\\name20220507T1047\\mask_rcnn_name_0010.h5", by_name=True)
#evaluate_model(test_set, model, cfg)

#%% [code]
# Predicting on test data
w=[]
h=[]
a=[]
id=[]
s=[]
d=[]
e=[]
#g=[]
import time
cap = cv2.VideoCapture(0)
time.sleep(2.0)
path_output_dir = 'C:\\Games\\Project\\images\\box-test\\'
count = 1
while (count <= 10):
        #cv2.waitKey(3000)
        success, image = cap.read()
        cv2.imshow("Frame",image) 
        
        if success:
            cv2.imwrite(os.path.join(path_output_dir, '%d.jpg') % count, image)
            count += 1
        else:
            break
cv2.destroyAllWindows()
cap.release()



import csv
from csv import writer

file = open(r'C:\Games\Project\barcodes.csv')
csvreader = csv.reader(file)

for i in range(1,2):
  path_to_new_image = 'C:\\Games\\Project\\images\\box-test\\'+str(i)+'.jpg'
  id.append(i)
  image = mpimg.imread(path_to_new_image)
  # Run object detection
  results1 = model.detect([image], verbose=1)
  # Display results
  ax = get_ax(1)
  r1 = results1[0]
  width=r1['rois'][0][2]-r1['rois'][0][0]
  w.append(width)
  height=r1['rois'][0][3]-r1['rois'][0][1]
  h.append(height)
  a.append(width*height)
  s.append(r1['scores'])
  d.append(r1['class_ids'])
  f=(csvreader)
  visualize.display_instances(image, r1['rois'], r1['masks'], r1['class_ids'],test_set.class_names, r1['scores'], ax=ax, title="Predictions")
  k=(test_set.class_names)
  e.append(k)
#Storing dimensions in a .csv file
#g=("damage")
for i in range(len(d)):
    if any((d[i]) == [2]):
       g=("Damage") 
    else:
      g=("No Damage")  
data={"Image ID":id,"Width":w,"Height":h,"Area": a,"scores": s,"class_id":d,"predictions":g,"Serial_id":f}
df = pd.DataFrame(data)
df.to_csv('C:\\Games\\Project\\images\\display\\Result_Dimension.csv', index=False)
if any(df.predictions=="Damage"):
  df.to_csv('C:\\Games\\Project\\images\\upload\\Result_Dimension.csv', index=False)
  path = r'C:\Games\Project\images\display\1.jpg'
  image = cv2.imread(path)
  window_name = 'box_image'
  cv2.imshow(window_name, image)
  cv2.waitKey(7000)
  cv2.destroyAllWindows()
  def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file), 
                       os.path.relpath(os.path.join(root, file), 
                                       os.path.join(path, r'C:\Games\Project\images\upload')))

  with zipfile.ZipFile('Outcome.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
    zipdir(r'C:\Games\Project\images\upload', zipf)

  
else:
  pass
    
'''def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file), 
                       os.path.relpath(os.path.join(root, file), 
                                       os.path.join(path, r'C:\Games\Project\images\display')))

with zipfile.ZipFile('Outcome.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
    zipdir(r'C:\Games\Project\images\display', zipf)'''
