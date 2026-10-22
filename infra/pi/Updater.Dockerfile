FROM docker:27-cli
RUN apk add --no-cache python3
COPY watch_main.py /opt/akgb/watch_main.py
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/opt/akgb/watch_main.py"]
