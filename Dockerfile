FROM python:alpine
RUN apk add tzdata
MAINTAINER Allan <atribe13@gmail.com>

WORKDIR /src
COPY requirements.txt /src/
RUN pip install --no-cache-dir -r requirements.txt
COPY envoy-local-influxdb-exporter.py /src/

CMD ["python", "-u", "/src/envoy-local-influxdb-exporter.py"]
