FROM projectmonai/monai
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf
RUN pip install -U pip
RUN pip install nvflare
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
