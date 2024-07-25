FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

RUN pytest --maxfail=1 --disable-warnings

ENV FLASK_APP=app.main:create_app()

CMD ["flask", "run", "--host=0.0.0.0", "--port=8000"]