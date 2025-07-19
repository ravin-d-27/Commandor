# Base Python image
FROM python:3.10-slim
WORKDIR /app
COPY . /app
RUN pip install --upgrade pip \
 && pip install .
CMD ["commandor"]
