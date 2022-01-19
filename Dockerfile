# --- Specify base image
FROM python:3.9.4-slim as builder

# --- Update and install packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc-dev && \
    apt-get clean

# --- Define a work directory which will hold files
WORKDIR /app

# --- Copy dependencies to container
COPY requirements.txt .

# --- Install dependencies in container
RUN pip install --upgrade pip && \
    pip install --user --no-warn-script-location -r requirements.txt

# --- Copy files to container
COPY . .
RUN pip install --user .


FROM python:3.9.4-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY main.py /app/

# --- Tell container to run application
CMD ["python", "./main.py"]