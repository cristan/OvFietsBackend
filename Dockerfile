FROM python:3.13.17-slim-trixie
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY vm_files/*.py vm_files/*.json ./
ENV PUBLIC_DIRECTORY=/srv/public
CMD ["python", "-u", "zmq_subscriber.py"]
