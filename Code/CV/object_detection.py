from PIL import Image

import matplotlib.pyplot as plt
import matplotlib
import os

from Code import ROOT

matplotlib.use("TkAgg")

img = Image.open(os.path.join(ROOT, "Datasets", "catdog.jpg"))
# plt.imshow(img)
# plt.show()
dog_bbox, cat_bbox = [60, 45, 378, 516], [400, 112, 655, 493]


def bbox_to_rect(bbox, color):
    # 将边界框模式(左上x,左上y,右下x,右下y)转换成matplotlib格式:
    # ((左上x,左上y),宽,高)
    return plt.Rectangle(xy=(bbox[0], bbox[1]), width=bbox[2]-bbox[0], height=bbox[3]-bbox[1],
                         fill=False, edgecolor=color, linewidth=2)


fig = plt.imshow(img)
fig.axes.add_patch(bbox_to_rect(dog_bbox, "blue"))
fig.axes.add_patch(bbox_to_rect(cat_bbox, "red"))
plt.show()