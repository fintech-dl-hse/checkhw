FROM ubuntu:25.04

WORKDIR /app/
COPY requirements.txt .

RUN apt update && apt-get upgrade -y && apt install -y curl python3-pip
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

RUN curl -k "https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer" -w "\n" >> $(python3 -m certifi)

COPY index.py sanic_index.py .

CMD ["python3", "sanic_index.py"]