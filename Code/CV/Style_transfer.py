import time
import torch
import torch.nn.functional as F
import torchvision
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib

from PIL import Image
import sys
from Code import DATADIR, MODELDIR

matplotlib.use("TkAgg")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

content_img = Image.open(os.path.join(DATADIR, "style_transfer", "rainier.jpg"))
# plt.imshow(content_img)
# plt.show()

style_img = Image.open(os.path.join(DATADIR, "style_transfer", "autumn_oak.jpg"))
# plt.imshow(style_img)
# plt.show()


rgb_mean = np.array([0.485, 0.456, 0.406])
rgb_std = np.array([0.229, 0.224, 0.225])


def preprocess(pil_image, image_shape):
    process = torchvision.transforms.Compose([
        torchvision.transforms.Resize(image_shape),
        torchvision.transforms.ToTensor(),
        torchvision.transforms.Normalize(mean=rgb_mean, std=rgb_std)
    ])
    return process(pil_image).unsqueeze(0)


def postprocess(img_tensor):
    inv_normalize = torchvision.transforms.Normalize(
        mean=-rgb_mean / rgb_std,
        std=1/rgb_std,
    )
    to_PIL_image = torchvision.transforms.ToPILImage()
    return to_PIL_image(inv_normalize(img_tensor[0].cpu()).clamp(0, 1))


# pytorch会将模型下载到TORCH_MODEL环境变量目录下，否则将会下载到.cache/torch下
os.environ["TORCH_HOME"] = MODELDIR
pretrianed_net = torchvision.models.vgg19(pretrained=True, progress=True)

# print(pretrianed_net)

style_layers = [0, 5, 10, 19, 28]
content_layers = [25]
net_list = []
for i in range(max(content_layers + style_layers) + 1):
    net_list.append(pretrianed_net.features[i])
net = torch.nn.Sequential(*net_list)


def extract_features(X, content_layers, style_layers):
    contents = []
    styles = []
    for i in range(len(net)):
        X = net[i](X)
        if i in style_layers:
            styles.append(X)
        if i in content_layers:
            contents.append(X)
    return contents, styles


def get_contents(image_shape, device):
    content_X = preprocess(content_img, image_shape).to(device)
    content_Y, _ = extract_features(content_X, content_layers, style_layers)
    return content_X, content_Y


def get_styles(image_shape, device):
    style_X = preprocess(style_img, image_shape).to(device)
    _, style_Y = extract_features(style_X, content_layers, style_layers)
    return style_X, style_Y


def content_loss(Y_hat, Y):
    return F.mse_loss(Y_hat, Y)


def gram(X):
    num_channels, n = X.shape[1], X.shape[2] * X.shape[3]
    X = X.view(num_channels, n)
    return torch.matmul(X, X.t()) / (num_channels * n)


def style_loss(Y_hat, gram_Y):
    return F.mse_loss(gram(Y_hat), gram_Y)


def tv_loss(Y_hat):
    return 0.5 * (F.l1_loss(Y_hat[:, :, 1:, :], Y_hat[:, :, :-1, :])) + \
                    F.l1_loss(Y_hat[:, :, :, 1:], Y_hat[:, :, :, :-1])


content_weight, style_weight, tv_weight = 1, 1e3, 10


def compute_loss(X, content_Y_hat, styles_Y_hat, content_Y, style_Y_gram):
    """分别计算内容损失，样式损失，总变差损失"""
    content_l = [content_loss(Y_hat, Y) * content_weight for Y_hat, Y in zip(content_Y_hat, content_Y)]
    style_l = [style_loss(Y_hat, Y) * style_weight for Y_hat, Y in zip(styles_Y_hat, style_Y_gram)]
    tv_l = tv_loss(X) * tv_weight
    # 对所有损失求和
    l = sum(style_l) + sum(content_l) + tv_l
    return content_l, style_l, tv_l, l


class GeneratedImage(torch.nn.Module):
    def __init__(self, image_shape):
        super(GeneratedImage, self).__init__()
        self.weight = torch.nn.Parameter(torch.rand(*image_shape))

    def forward(self):
        return self.weight


def get_inits(X, device, lr, styles_Y):
    gen_img = GeneratedImage(X.shape).to(device)
    gen_img.weight.data = X.data
    optimizer = torch.optim.Adam(gen_img.parameters(), lr=lr)
    styles_Y_gram = [gram(Y) for Y in styles_Y]
    return gen_img(), styles_Y_gram, optimizer


def train_st(X, content_Y, styles_Y, device, lr, max_epochs, lr_decay_epoch):
    print("training on %s" % device)
    X, styles_Y_gram, optimizer = get_inits(X, device, lr, styles_Y)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, lr_decay_epoch, gamma=0.1)
    for i in range(max_epochs):
        start = time.time()

        contents_Y_hat, styles_Y_hat = extract_features(X, content_layers, style_layers)
        contents_l, styles_l, tv_l, l = compute_loss(X, contents_Y_hat, styles_Y_hat, content_Y, styles_Y_gram)
        optimizer.zero_grad()
        l.backward(retain_graph=True)
        optimizer.step()
        scheduler.step()
        if i % 50 == 0 and i != 0:
            print("epoch %d, content loss %.2f, style loss %.2f, TV loss %.2f, %.2f sec" % \
                  (i, sum(contents_l).item(), sum(styles_l).item(), tv_l.item(), time.time()-start))
    return X.detach()


if __name__ == '__main__':
    image_shape = (150, 225)
    net = net.to(device)
    content_X, content_Y = get_contents(image_shape, device)
    style_X, style_Y = get_styles(image_shape, device)
    output = train_st(content_X, content_Y, style_Y, device, lr=0.01, max_epochs=500, lr_decay_epoch=200)
    plt.imshow(postprocess(output))
    plt.show()