FROM projectmonai/monai
RUN pip install -U pip
RUN pip install nvflare
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
ENV PYTHONPATH="/code"
