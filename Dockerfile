FROM core:11.4.2-cudnn8-runtime-ubuntu20.04

RUN pip3 install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu113
RUN pip3 install scipy

#RUN pip install inflect==4.1.0
RUN pip install scipy==1.5.0
RUN pip install tqdm
#RUN pip install pesq
#RUN pip install pystoi
RUN pip install asteroid

#CMD python3 model/train.py
