import streamlit as st
from playwright.sync_api import sync_playwright
import os
import time

# ==========================================
# PREPARAÇÃO DO AMBIENTE NA NUVEM
# ==========================================
@st.cache_resource(show_spinner=False)
def instalar_navegador():
    # Força a instalação do Chromium no servidor Linux do Streamlit
    os.system("playwright install chromium")

instalar_navegador()

# ==========================================
# INTERFACE DO USUÁRIO (MANTIDA INTACTA)
# ==========================================
st.set_page_config(page_title="Emissor ITBI/CND", page_icon="📄")

st.title("📄 Automação de Tributos - Elmar")
st.markdown("Preencha os dados abaixo para gerar a CND e a Guia de ITBI automaticamente.")

with st.form("dados_form"):
    col1, col2 = st.columns(2)
    with col1:
        inscricao = st.text_input("Inscrição Imobiliária", placeholder="Ex: 123456")
        cpf_prop = st.text_input("CPF/CNPJ do Vendedor", placeholder="000.000.000-00")
    with col2:
        cpf_compr = st.text_input("CPF/CNPJ do Comprador", placeholder="000.000.000-00")
    
    submit_button = st.form_submit_button("Gerar Documentos")

# ==========================================
# MOTOR DE AUTOMAÇÃO
# ==========================================
def gerar_documentos(insc, prop, compr):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        documentos = {}

        try:
            # 0. Sessão
            page.goto("https://tributos.elmartecnologia.com.br/portal/?ecode=201082")
            time.sleep(2)

            # 1. CND
            with st.spinner("Gerando CND..."):
                page.goto("https://tributos.elmartecnologia.com.br/portal/buscaCertidaoImob.php")
                page.fill("#vINSCRICAO", insc)
                with context.expect_page() as popup_info:
                    page.click("#enviarINSCRICAO")
                aba_cnd = popup_info.value
                aba_cnd.wait_for_load_state("networkidle")
                pdf_cnd = aba_cnd.pdf(format="A4", print_background=True)
                documentos['cnd'] = pdf_cnd
                aba_cnd.close()

            # 2. ITBI
            with st.spinner("Gerando Guia de ITBI..."):
                page.goto("https://tributos.elmartecnologia.com.br/portal/buscaITBI.php")
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

            return documentos

        except Exception as e:
            st.error(f"Erro durante a navegação do robô: {e}")
            return None
        finally:
            browser.close()

# ==========================================
# EXECUÇÃO APÓS O CLIQUE
# ==========================================
if submit_button:
    if not inscricao or not cpf_prop or not cpf_compr:
        st.warning("Por favor, preencha todos os campos.")
    else:
        res = gerar_documentos(inscricao, cpf_prop, cpf_compr)
        
        if res:
            st.success("Documentos gerados com sucesso!")
            col_d1, col_d2 = st.columns(2)
            
            with col_d1:
                st.download_button(
                    label="⬇️ Baixar CND",
                    data=res['cnd'],
                    file_name=f"CND_{inscricao}.pdf",
                    mime="application/pdf"
                )
            
            with col_d2:
                st.download_button(
                    label="⬇️ Baixar Guia ITBI",
                    data=res['itbi'],
                    file_name=f"ITBI_{inscricao}.pdf",
                    mime="application/pdf"
                )
