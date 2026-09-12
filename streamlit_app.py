import streamlit as st
from playwright.sync_api import sync_playwright
import time
import pdfplumber
import re

# ==========================================
# INTERFACE DO USUÁRIO & ESTADO
# ==========================================
st.set_page_config(page_title="Emissor ITBI/CND", page_icon="📄")

# Cria a memória para o auto-preenchimento
if 'auto_insc' not in st.session_state:
    st.session_state.auto_insc = ""
if 'auto_prop' not in st.session_state:
    st.session_state.auto_prop = ""
if 'auto_compr' not in st.session_state:
    st.session_state.auto_compr = ""

st.title("📄 Automação de Tributos - Elmar")
st.markdown("Faça o upload do Boleto de ITBI para preencher os dados automaticamente ou digite manualmente.")

# ==========================================
# CÉREBRO DE EXTRAÇÃO DO PDF
# ==========================================
def extrair_dados_pdf(arquivo_pdf):
    texto_completo = ""
    try:
        with pdfplumber.open(arquivo_pdf) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto_completo += texto_pagina + "\n"
        
        # Expressões Regulares (Regex) para encontrar os padrões no texto
        inscricao = ""
        # Procura "Inscr. do Imóvel:" ignorando espaços ou quebras de linha até achar o número
        match_insc = re.search(r'Inscr\.\s*do\s*Imóvel:\s*(\d+)', texto_completo, re.IGNORECASE)
        if match_insc:
            inscricao = match_insc.group(1)
            
        # Procura todos os padrões "CPF/CNPJ: 000.000.000-00"
        cpfs = re.findall(r'CPF/CNPJ:\s*([\d\.\-\/]+)', texto_completo, re.IGNORECASE)
        
        cpf_prop = cpfs[0] if len(cpfs) > 0 else ""
        cpf_compr = cpfs[1] if len(cpfs) > 1 else ""
        
        return inscricao, cpf_prop, cpf_compr
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
        return "", "", ""

# ==========================================
# ÁREA DE UPLOAD
# ==========================================
arquivo_up = st.file_uploader("Arraste o Boleto de ITBI aqui (PDF)", type=["pdf"])

if arquivo_up is not None:
    # Só faz a extração se ainda não tiver feito para esse arquivo
    if st.session_state.get('ultimo_arquivo') != arquivo_up.name:
        with st.spinner("Lendo documento..."):
            insc, prop, compr = extrair_dados_pdf(arquivo_up)
            
            # Alimenta a memória do Streamlit
            st.session_state.auto_insc = insc
            st.session_state.auto_prop = prop
            st.session_state.auto_compr = compr
            st.session_state.ultimo_arquivo = arquivo_up.name
            
            st.success("Dados extraídos! Confira abaixo antes de gerar.")

st.markdown("---")

# ==========================================
# FORMULÁRIO (AUTO-PREENCHIDO)
# ==========================================
with st.form("dados_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        # Usa o value conectado ao session_state
        inscricao = st.text_input("Inscrição Imobiliária", value=st.session_state.auto_insc)
    with col2:     
        cpf_prop = st.text_input("CPF/CNPJ do Vendedor", value=st.session_state.auto_prop)
    with col3:
        cpf_compr = st.text_input("CPF/CNPJ do Comprador", value=st.session_state.auto_compr)
    
    submit_button = st.form_submit_button("Gerar Documentos")

# ==========================================
# MOTOR DE AUTOMAÇÃO (Navegação Web)
# ==========================================
def gerar_documentos(insc, prop, compr):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--no-zygote",          
                "--single-process",     
                "--disable-features=site-per-process" 
            ]
        )
        
        context = browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        documentos = {}

        try:
            page.goto(
                "https://tributos.elmartecnologia.com.br/portal/?ecode=201082", 
                wait_until="domcontentloaded",
                timeout=60000
            )
            time.sleep(2)

            # --- CND ---
            with st.spinner("Gerando CND..."):
                page.goto("https://tributos.elmartecnologia.com.br/portal/buscaCertidaoImob.php", wait_until="domcontentloaded", timeout=60000)
                try:
                    page.locator("#vINSCRICAO").wait_for(state="visible", timeout=30000)
                    page.fill("#vINSCRICAO", insc)
                    with context.expect_page() as popup_info:
                        page.click("#enviarINSCRICAO")
                    
                    aba_cnd = popup_info.value
                    aba_cnd.wait_for_load_state("networkidle")
                    pdf_cnd = aba_cnd.pdf(format="A4", print_background=True)
                    documentos['cnd'] = pdf_cnd
                    aba_cnd.close()
                except Exception as e:
                    page.screenshot(path="visao_do_robo_cnd.png")
                    st.error("Erro na CND. Veja a tela:")
                    st.image("visao_do_robo_cnd.png")
                    raise e 

            # --- ITBI ---
            with st.spinner("Gerando Guia de ITBI..."):
                page.goto("https://tributos.elmartecnologia.com.br/portal/buscaITBI.php", wait_until="domcontentloaded", timeout=60000)
                try:
                    page.locator("#INSCRICAO").wait_for(state="visible", timeout=30000)
                    page.fill("#INSCRICAO", insc)
                    page.fill("#CPF_PROP", prop)
                    page.fill("#CPF_COMPR", compr)
                    with context.expect_page() as popup_info:
                        page.click("#enviarINSCRICAO")
                    
                    aba_itbi = popup_info.value
                    aba_itbi.wait_for_load_state("networkidle")
                    pdf_itbi = aba_itbi.pdf(format="A4", print_background=True)
                    documentos['itbi'] = pdf_itbi
                    aba_itbi.close()
                except Exception as e:
                    page.screenshot(path="visao_do_robo_itbi.png")
                    st.error("Erro no ITBI. Veja a tela:")
                    st.image("visao_do_robo_itbi.png")
                    raise e

            return documentos

        except Exception as e:
            st.error(f"Erro durante a navegação do robô: {e}")
            return None
        finally:
            browser.close()

# ==========================================
# EXECUÇÃO APÓS O CLIQUE
# ==========================================
if 'arquivos_gerados' not in st.session_state:
    st.session_state.arquivos_gerados = None
    st.session_state.inscricao_salva = ""

if submit_button:
    if not inscricao or not cpf_prop or not cpf_compr:
        st.warning("Por favor, preencha todos os campos.")
    else:
        st.session_state.arquivos_gerados = None 
        res = gerar_documentos(inscricao, cpf_prop, cpf_compr)
        
        if res:
            st.session_state.arquivos_gerados = res
            st.session_state.inscricao_salva = inscricao
            st.success("Documentos gerados com sucesso!")

if st.session_state.arquivos_gerados:
    st.markdown("---")
    st.markdown("### 🗂️ Arquivos Prontos")
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
        st.download_button(label="⬇️ Baixar CND", data=st.session_state.arquivos_gerados['cnd'], file_name=f"CND_{st.session_state.inscricao_salva}.pdf", mime="application/pdf")
    
    with col_d2:
        st.download_button(label="⬇️ Baixar Guia ITBI", data=st.session_state.arquivos_gerados['itbi'], file_name=f"ITBI_{st.session_state.inscricao_salva}.pdf", mime="application/pdf")
                    
