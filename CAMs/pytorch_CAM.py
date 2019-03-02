# Fangyu @EPFL, Lausanne, June 25, 2018
# edited from:
# https://raw.githubusercontent.com/metalbubble/CAM/master/pytorch_CAM.py


# simple implementation of CAM in PyTorch for the networks such as ResNet, DenseNet, SqueezeNet, Inception

import io
import requests
import os
from PIL import Image
from torchvision import models, transforms
from torch.autograd import Variable
from torch.nn import functional as F
import torch
import random
import string
from collections import OrderedDict

import torch._utils
try:
    torch._utils._rebuild_tensor_v2
except AttributeError:
    def _rebuild_tensor_v2(storage, storage_offset, size, stride, requires_grad, backward_hooks):
        tensor = torch._utils._rebuild_tensor(storage, storage_offset, size, stride)
        tensor.requires_grad = requires_grad
        tensor._backward_hooks = backward_hooks
        return tensor
    torch._utils._rebuild_tensor_v2 = _rebuild_tensor_v2

import numpy as np
import cv2
import pdb
import sys
from CAM_utils import model_wrapper

# input image
# LABELS_URL = 'https://s3.amazonaws.com/outcome-blog/imagenet/labels.json'
# IMG_URL = 'http://media.mlive.com/news_impact/photo/9933031-large.jpg'


net = models.resnet50(pretrained=False)
pre = torch.load('resnet50-400.pth')
new = OrderedDict()
for i,v in pre.items():
    if 'model' in i:
        new_key = i[i.find('.')+1:]
        new[new_key] = v

net.load_state_dict(new)
finalconv_name = 'layer4'
        #model_name = 'resnet152'
        #model_name = 'resnet101'
model_name = 'resnet50'
# model_name = 'resnet34'

net.eval()

# hook the feature extractor
features_blobs = []
def hook_feature(module, input, output):
    features_blobs.append(output.data.cpu().numpy())

net._modules.get(finalconv_name).register_forward_hook(hook_feature)


# get the softmax weight
params = list(net.parameters())
weight_softmax = np.squeeze(params[-2].data.numpy())

def returnCAM(feature_conv, weight_softmax, class_idx):
    # generate the class activation maps upsample to 256x256
    size_upsample = (256, 256)
    bz, nc, h, w = feature_conv.shape
    output_cam = []
    for idx in class_idx:
        cam = weight_softmax[idx].dot(feature_conv.reshape((nc, h*w)))
        cam = cam.reshape(h, w)
        cam = cam - np.min(cam)
        cam_img = cam / np.max(cam)
        cam_img = np.uint8(255 * cam_img)
        output_cam.append(cv2.resize(cam_img, size_upsample))
    return output_cam


normalize = transforms.Normalize(
   mean=[0.485, 0.456, 0.406],
   std=[0.229, 0.224, 0.225]
)
preprocess = transforms.Compose([
   transforms.Resize((224,224)),
   transforms.ToTensor(),
   normalize
])

#response = requests.get(IMG_URL)
#img_pil = Image.open(io.BytesIO(response.content))


folders = os.listdir(sys.argv[1])
for folder in folders:
    if not os.path.isdir(os.path.join(sys.argv[1],folder)):
        print (os.path.join(sys.argv[1],folder),'not dir. Continue.')
        continue
    pics = os.listdir(os.path.join(sys.argv[1],folder))
    for pic in pics:
        img_pil = None
        if (not pic.endswith('.jpg')) and (not pic.endswith('.png')):
            print ('skip',pic)
            continue
#         if 'done' not in pic: continue
        pic_path = os.path.join(sys.argv[1],folder,pic)
        print (pic_path)
        img_pil = Image.open(pic_path).convert("RGB")
        img_pil.save('test.jpg')
        
        img_tensor = preprocess(img_pil)
        img_variable = Variable(img_tensor.unsqueeze(0))
        logit = net(img_variable)\
        
        # download the imagenet category list
        #classes = {int(key):value for (key, value)
        #          in requests.get(LABELS_URL).json().items()}
        h_x = F.softmax(logit, dim=1).data.squeeze()
        probs, idx = h_x.sort(0, True)
        probs = probs.numpy()
        idx = idx.numpy()
        # output the prediction
        #for i in range(0, 5):
        #    print('{:.3f} -> {}'.format(probs[i], classes[idx[i]]))
        # generate class activation mapping for the top1 prediction
        CAMs = returnCAM(features_blobs[0], weight_softmax, [idx[0]])
        # render the CAM and output
        # print('output CAM.jpg for the top1 prediction: %s'%classes[idx[0]])
        img = cv2.imread('test.jpg')
        height, width, _ = img.shape
        heatmap = cv2.applyColorMap(cv2.resize(CAMs[0],(width, height)), cv2.COLORMAP_JET)
        result = heatmap * 0.3 + img * 0.5
        #cv2.imwrite('CAM-'+ sys.argv[1].split('/')[-1].split('.')[0] +'-'+sys.argv[2].split('/')[-1].split('.')[0]+'.jpg', result)
#         random_string = random.choice(string.ascii_letters) + random.choice(string.ascii_letters) + random.choice(string.ascii_letters)
        print(result)
        cv2.imwrite('CAM-'+folder+'-'+pic.split('.')[0]+'-'+model_name+'.jpg', result)
        print ('wrote to','new_CAM_pics_3/'+'CAM-'+folder+'-'+pic.split('.')[0]+'.jpg')

