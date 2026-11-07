import streamlit as st
from playwright.sync_api import sync_playwright
import time
import pdfplumber
import re
import pandas as pd
import io
import zipfile

st.set_page_config(page_title="Emissor ITBI/CND em Lote", page_icon="📑", layout="wide")

# ==========================================
# CÉREBRO DE EXTRAÇÃO DO PDF
# ==========================================
def extrair_dados_pdf(arquivo_pdf):
    texto_completo = ""
    try:
        with pdfplumber.open(arquivo_pdf) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text(layout=True)
                if texto:
                    texto_completo += texto + "\n"

        inscricao = ""
        match_insc = re.search(r'(?:Inscr|Inser|Im[oó]vel)[^\d]*?(\d{10,20})', texto_completo, re.IGNORECASE | re.DOTALL)
        if match_insc:
            inscricao = match_insc.group(1)
        else:
            match_insc_fallback = re.search(r'(?<![\.\-\/])\b(\d{14})\b(?![\.\-\/])', texto_completo)
            if match_insc_fallback:
                inscricao = match_insc_fallback.group(1)
            
        cpfs = re.findall(r'CPF/CNPJ:\s*([\d\.\-\/]+)', texto_completo, re.IGNORECASE)
        
        cpf_prop = cpfs[0] if len(cpfs) > 0 else ""
        cpf_compr = cpfs[1] if len(cpfs) > 1 else ""
        
        return inscricao, cpf_prop, cpf_compr
    except Exception:
        return "", "", ""

# ==========================================
# GESTÃO DE ESTADO E ARQUIVOS
# ==========================================
if 'df_dados' not in st.session_state:
    # Cria a estrutura inicial da tabela
    st.session_state.df_dados = pd.DataFrame(columns=["Arquivo", "Inscrição", "CPF Vendedor", "CPF Comprador"])
if 'arquivos_anteriores' not in st.session_state:
    st.session_state.arquivos_anteriores = []
if 'arquivo_zip_pronto' not in st.session_state:
    st.session_state.arquivo_zip_pronto = None

st.title("📑 Emissor em Lote - Tributos Elmar")
st.markdown("Arraste **vários** boletos ao mesmo tempo. Os dados formarão uma tabela que você pode revisar e editar antes de emitir.")

# ==========================================
# 1. ÁREA DE UPLOAD (MÚLTIPLOS ARQUIVOS)
# ==========================================
uploaded_files = st.file_uploader("Arraste os Boletos de ITBI aqui (PDFs)", type=["pdf"], accept_multiple_files=True)

# Lógica para só reprocessar se o usuário colocar/tirar um arquivo novo
nomes_atuais = [f.name for f in uploaded_files] if uploaded_files else []

if nomes_atuais != st.session_state.arquivos_anteriores:
    dados_extraidos = []
    if uploaded_files:
        with st.spinner("Lendo todos os documentos..."):
            for file in uploaded_files:
                insc, prop, compr = extrair_dados_pdf(file)
                dados_extraidos.append({
                    "Arquivo": file.name,
                    "Inscrição": insc,
                    "CPF Vendedor": prop,
                    "CPF Comprador": compr
                })
        # Atualiza a tabela na memória
        st.session_state.df_dados = pd.DataFrame(dados_extraidos)
    else:
        # Se esvaziar a caixa, limpa a tabela
        st.session_state.df_dados = pd.DataFrame(columns=["Arquivo", "Inscrição", "CPF Vendedor", "CPF Comprador"])
    
    st.session_state.arquivos_anteriores = nomes_atuais
    st.rerun()

st.markdown("---")

# ==========================================
# 2. TABELA INTERATIVA DE VALIDAÇÃO
# ==========================================
st.markdown("### 📋 Tabela de Dados (Revise ou edite os números abaixo)")

# st.data_editor permite que você clique e altere os números como no Excel
df_editado = st.data_editor(
    st.session_state.df_dados, 
    num_rows="dynamic", # Permite adicionar linhas manualmente se não quiser usar PDF
    use_container_width=True,
    hide_index=True
)

submit_button = st.button("🚀 Gerar Lote de Documentos", type="primary")

# ==========================================
# 3. MOTOR DE AUTOMAÇÃO EM LOTE
# ==========================================
def gerar_lote_zip(df_valido):
    # Cria o arquivo ZIP invisível na memória do servidor
    zip_buffer = io.BytesIO()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--no-zygote", "--single-process", "--disable-features=site-per-process"]
        )
        context = browser.new_context(accept_downloads=True, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        
        # Abre o arquivo ZIP para começarmos a colocar os PDFs dentro
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            
            # Conta o progresso
            total_arquivos = len(df_valido)
            barra_progresso = st.progress(0)
            status_texto = st.empty()

            try:
                # Login / Autenticação (feita 1 vez só)
                status_texto.text("Acessando sistema Elmar...")
                page.goto("https://tributos.elmartecnologia.com.br/portal/?ecode=201082", wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)
                
                # Loop por cada linha da tabela
                for index, row in df_valido.iterrows():
                    insc = str(row['Inscrição']).strip()
                    prop = str(row['CPF Vendedor']).strip()
                    compr = str(row['CPF Comprador']).strip()
                    
                    status_texto.text(f"Emitindo Inscrição: {insc} ({index+1}/{total_arquivos})")
                    
                    # --- CND ---
                    page.goto("https://tributos.elmartecnologia.com.br/portal/buscaCertidaoImob.php", wait_until="domcontentloaded", timeout=60000)
                    page.locator("#vINSCRICAO").wait_for(state="visible", timeout=30000)
                    page.fill("#vINSCRICAO", insc)
                    with context.expect_page() as popup_cnd:
                        page.click("#enviarINSCRICAO")
                    
                    aba_cnd = popup_cnd.value
                    aba_cnd.wait_for_load_state("networkidle")
                    pdf_cnd = aba_cnd.pdf(format="A4", print_background=True)
                    zip_file.writestr(f"CND_{insc}.pdf", pdf_cnd) # Salva no ZIP
                    aba_cnd.close()

                    # --- ITBI ---
                    page.goto("https://tributos.elmartecnologia.com.br/portal/buscaITBI.php", wait_until="domcontentloaded", timeout=60000)
                    page.locator("#INSCRICAO").wait_for(state="visible", timeout=30000)
                    page.fill("#INSCRICAO", insc)
                    page.fill("#CPF_PROP", prop)
                    page.fill("#CPF_COMPR", compr)
                    with context.expect_page() as popup_itbi:
                        page.click("#enviarINSCRICAO")
                    
                    aba_itbi = popup_itbi.value
                    aba_itbi.wait_for_load_state("networkidle")
                    pdf_itbi = aba_itbi.pdf(format="A4", print_background=True)
                    zip_file.writestr(f"ITBI_{insc}.pdf", pdf_itbi) # Salva no ZIP
                    aba_itbi.close()
                    
                    # Atualiza a barra de progresso
                    barra_progresso.progress((index + 1) / total_arquivos)

            except Exception as e:
                page.screenshot(path="erro_automacao.png")
                st.error("Erro na navegação do robô durante o lote. Veja a tela onde ele parou:")
                st.image("erro_automacao.png")
                browser.close()
                return None
                
        browser.close()
        
    status_texto.text("Lote concluído com sucesso!")
    return zip_buffer.getvalue()

# ==========================================
# 4. EXECUÇÃO E REGRAS DE NEGÓCIO (A TRAVA DE SEGURANÇA)
# ==========================================
if submit_button:
    st.session_state.arquivo_zip_pronto = None
    
    # Remove linhas vazias se o usuário criou linha na tabela e não preencheu
    df_valido = df_editado.dropna(subset=['Inscrição', 'CPF Vendedor', 'CPF Comprador'], how='all')
    df_valido = df_valido.fillna("")
    
    if df_valido.empty:
        st.warning("A tabela está vazia. Suba os boletos ou preencha manualmente.")
    else:
        tem_erro = False
        
        # CHECAGEM 1: Campos em branco e CHECAGEM 2: Inconsistência de CPF idêntico
        for idx, row in df_valido.iterrows():
            insc = str(row['Inscrição']).strip()
            prop = str(row['CPF Vendedor']).strip()
            compr = str(row['CPF Comprador']).strip()
            
            if not insc or not prop or not compr:
                st.error(f"⚠️ A Inscrição '{insc}' possui campos em branco na tabela. Preencha todos os dados antes de gerar.")
                tem_erro = True
                break
                
            if prop == compr:
                st.error(f"🚨 INCONSISTÊNCIA DETECTADA: Na inscrição **{insc}**, o CPF do Vendedor ({prop}) é idêntico ao do Comprador. Geração abortada por segurança.")
                tem_erro = True
                break
        
        # Se passou em todas as regras de segurança, chama o robô!
        if not tem_erro:
            resultado_zip = gerar_lote_zip(df_valido)
            if resultado_zip:
                st.session_state.arquivo_zip_pronto = resultado_zip
                st.success("🎉 Todos os documentos foram gerados e empacotados!")

# Botão final para baixar o ZIP
if st.session_state.arquivo_zip_pronto:
    st.markdown("---")
    st.markdown("### 🗂️ Lote Pronto para Download")
    st.download_button(
        label="⬇️ BAIXAR LOTE COMPLETO (.ZIP)",
        data=st.session_state.arquivo_zip_pronto,
        file_name="Lote_Documentos_ITBI.zip",
        mime="application/zip",
        type="primary"
    )
