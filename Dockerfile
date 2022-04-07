# --- Specify base image
FROM python:3.9.4-slim

COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
ENTRYPOINT ["streamlit", "run"]
CMD ["app.py"]