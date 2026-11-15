FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY app.py worksheet.py index.html ./
ENV APP_HOST=0.0.0.0 PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8000
CMD ["python", "app.py"]
