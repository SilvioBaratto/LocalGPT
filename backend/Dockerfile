FROM python:3.11-slim

WORKDIR /code 

COPY ./requirements.txt ./

RUN apt-get update 

RUN pip install --no-cache-dir -r requirements.txt

COPY . ./src

EXPOSE 8080

CMD ["gunicorn", "src.app:app", "--bind", "0.0.0.0:8080", "--workers 4"]