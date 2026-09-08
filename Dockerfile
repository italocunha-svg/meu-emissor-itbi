FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD sh -c "streamlit run streamlit_app.py --server.port ${PORT:-10000} --server.address 0.0.0.0"
