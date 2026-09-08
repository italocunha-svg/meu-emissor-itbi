# Usa a imagem oficial da Microsoft que JÁ VEM com o navegador e todas as peças gráficas
FROM [mcr.microsoft.com/playwright/python:v1.62.0-jammy](https://mcr.microsoft.com/playwright/python:v1.62.0-jammy)

# Define a pasta de trabalho dentro do servidor
WORKDIR /app

# Copia todos os seus arquivos do GitHub para o servidor
COPY . .

# Instala as bibliotecas do Python (Streamlit, etc)
RUN pip install --no-cache-dir -r requirements.txt

# Comando universal para ligar o emissor na porta correta do Render
CMD sh -c "streamlit run streamlit_app.py --server.port ${PORT:-10000} --server.address 0.0.0.0"
