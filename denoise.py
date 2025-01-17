# Adapted from https://github.com/NVIDIA/waveglow under the BSD 3-Clause License.

# *****************************************************************************
#  Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of the NVIDIA CORPORATION nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL NVIDIA CORPORATION BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# *****************************************************************************

import os
import argparse
import json
from tqdm import tqdm
from copy import deepcopy

import numpy as np
import torch
import torch.nn as nn
# from torch.utils.tensorboard import SummaryWriter

import random
random.seed(0)
torch.manual_seed(0)
np.random.seed(0)

from scipy.io.wavfile import write as wavwrite
from scipy.io.wavfile import read as wavread

from dataset import load_CleanNoisyPairDataset
from util import rescale, find_max_epoch, print_size, sampling
from network import CleanUNet
from time import sleep


def denoise(output_directory, ckpt_iter, subset, dump=False):
    """
    Denoise audio

    Parameters:
    output_directory (str):         save generated speeches to this path
    ckpt_iter (int or 'max'):       the pretrained checkpoint to be loaded;
                                    automitically selects the maximum iteration if 'max' is selected
    subset (str):                   training, testing, validation
    dump (bool):                    whether save enhanced (denoised) audio
    """

    # setup local experiment path
    exp_path = train_config["exp_path"]
    print('exp_path:', exp_path)

    # load data
    loader_config = deepcopy(trainset_config)
    loader_config["crop_length_sec"] = 0
    dataloader, n_files = load_CleanNoisyPairDataset(
        **loader_config,
        subset=subset,
        batch_size=1,
        num_gpus=1
    )

    # predefine model
    net = CleanUNet(**network_config).cuda()
    net_cpu = CleanUNet(**network_config)

    """
    net = LambdaOverlapAdd(
             nnet=net,
             n_src=2,
             window_size=64000,
             hop_size=None,
             window="hanning",
             reorder_chunks=True,
             enable_grad=False,
         )
    """
    print_size(net)

    # load checkpoint
    ckpt_directory = os.path.join(train_config["log"]["directory"], 'checkpoint')
    print(ckpt_directory)
    if ckpt_iter == 'max':
        ckpt_iter = find_max_epoch(ckpt_directory)
    if ckpt_iter != 'pretrained':
        ckpt_iter = int(ckpt_iter)
    model_path = os.path.join(ckpt_directory, '{}.pkl'.format(ckpt_iter))
    checkpoint = torch.load(model_path, map_location='cpu')
    net.load_state_dict(checkpoint['model_state_dict'])
    net.eval()

    # get output directory ready
    if ckpt_iter == "pretrained":
        speech_directory = os.path.join(output_directory, exp_path, 'denoised', ckpt_iter)
    else:
        speech_directory = os.path.join(output_directory, exp_path, 'denoised', '{}k'.format(ckpt_iter//1000))
    if dump and not os.path.isdir(speech_directory):
        os.makedirs(speech_directory)
        os.chmod(speech_directory, 0o775)
    print("speech_directory: ", speech_directory, flush=True)

    # inference
    all_generated_audio = []
    all_clean_audio = []
    sortkey = lambda name: '_'.join(name.split('/')[-1].split('_')[1:])
    for noisy_audio, fileid in tqdm(dataloader):
        filename = sortkey(fileid[0])
        LENGTH = len(noisy_audio[0].squeeze())
        print(LENGTH/8000 )
        try:
            generated_audio = sampling(net, noisy_audio.cuda())
            out_audio = generated_audio[0].squeeze().cpu().numpy()
        except RuntimeError as e:
            print(e)
            sleep(2)
            generated_audio = sampling(net_cpu, noisy_audio)
            out_audio = generated_audio[0].squeeze().numpy()
        print(filename)
        if dump:
            print(os.path.join(speech_directory, 'fileid_{}'.format(filename)))
            wavwrite(os.path.join(speech_directory, 'fileid_{}'.format(filename)),
                    trainset_config["sample_rate"],
                    out_audio)
        else:
            all_generated_audio.append(out_audio)
        torch.cuda.empty_cache()
    return all_clean_audio, all_generated_audio


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', type=str, default='config.json',
                        help='JSON file for configuration')
    parser.add_argument('-ckpt_iter', '--ckpt_iter', default='max',
                        help='Which checkpoint to use; assign a number or "max" or "pretrained"')
    parser.add_argument('-subset', '--subset', type=str, choices=['training', 'testing', 'validation'],
                        default='testing', help='subset for denoising')
    args = parser.parse_args()

    # Parse configs. Globals nicer in this case
    with open(args.config) as f:
        data = f.read()
    config = json.loads(data)
    gen_config              = config["gen_config"]
    global network_config
    network_config          = config["network_config"]      # to define wavenet
    global train_config
    train_config            = config["train_config"]        # train config
    global trainset_config
    trainset_config         = config["trainset_config"]     # to read trainset configurations

    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.benchmark = True

    if args.subset == "testing":
        denoise(gen_config["output_directory"],
                subset=args.subset,
                ckpt_iter=args.ckpt_iter,
                dump=True)
