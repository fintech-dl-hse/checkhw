FROM python:3.11-alpine

COPY index.py sanic_index.py requirements.txt /app/

RUN cd /app && pip install --no-cache-dir -r requirements.txt && apk add --no-cache curl
RUN curl -k "https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer" -w "\n" >> $(python -m certifi)

WORKDIR /app
CMD ["python", "sanic_index.py"]