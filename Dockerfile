FROM core:11.4.2-cudnn8-runtime-ubuntu20.04

RUN pip3 install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu113
RUN pip3 install scipy

#RUN pip install inflect==4.1.0
RUN pip install scipy==1.5.0
RUN pip install tqdm
RUN pip install asteroid

RUN apt install libsndfile1 -y

RUN pip install librosa
RUN pip install soundfile
RUN pip install numpy==1.20.3
