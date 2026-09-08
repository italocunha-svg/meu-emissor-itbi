import streamlit as st
from playwright.sync_api import sync_playwright
import time

# ==========================================
# INTERFACE DO USUÁRIO
# ==========================================
st.set_page_config(page_title="Emissor ITBI/CND", page_icon="📄")

st.title("📄 Automação de Tributos - Elmar")
st.markdown("Preencha os dados abaixo para gerar a CND e a Guia de ITBI automaticamente.")

with st.form("dados_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        inscricao = st.text_input("Inscrição Imobiliária", placeholder="Ex: 123456")
    with col2:     
        cpf_prop = st.text_input("CPF/CNPJ do Vendedor", placeholder="000.000.000-00")
    with col3:
        cpf_compr = st.text_input("CPF/CNPJ do Comprador", placeholder="000.000.000-00")
    
    submit_button = st.form_submit_button("Gerar Documentos")

# ==========================================
# MOTOR DE AUTOMAÇÃO
# ==========================================
def gerar_documentos(insc, prop, compr):
    with sync_playwright() as p:
        # Configuração máxima de sobrevivência para nuvem
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--no-zygote",          # Evita a pré-alocação de memória do Chrome
                "--single-process",     # Força o navegador a rodar em uma única thread
                "--disable-features=site-per-process" # Remove o isolamento de segurança pesado
            ]
        )
        
        context = browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        documentos = {}

        try:
            # =========================================================
            # 0. Sessão (Autenticação)
            # =========================================================
            page.goto(
                "https://tributos.elmartecnologia.com.br/portal/?ecode=201082", 
                wait_until="domcontentloaded",
                timeout=60000
            )
            time.sleep(2)

            # =========================================================
            # 1. CND
            # =========================================================
            with st.spinner("Gerando CND..."):
                page.goto(
                    "https://tributos.elmartecnologia.com.br/portal/buscaCertidaoImob.php",
                    wait_until="domcontentloaded",
                    timeout=60000
                )
                
                try:
                    # Trava para garantir que o campo carregou e captura de tela em caso de falha
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
                    st.error("O robô não encontrou o campo de Inscrição na CND. Veja o que ele está enxergando na tela:")
                    st.image("visao_do_robo_cnd.png")
                    raise e # Interrompe a execução e pula para o fechamento

            # =========================================================
            # 2. ITBI
            # =========================================================
            with st.spinner("Gerando Guia de ITBI..."):
                page.goto(
                    "https://tributos.elmartecnologia.com.br/portal/buscaITBI.php",
                    wait_until="domcontentloaded",
                    timeout=60000
                )
                
                try:
                    # Captura de tela para ITBI também, caso mude o padrão
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
                    st.error("O robô não encontrou o campo de Inscrição no ITBI. Veja o que ele está enxergando na tela:")
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
        st.download_button(
            label="⬇️ Baixar CND",
            data=st.session_state.arquivos_gerados['cnd'],
            file_name=f"CND_{st.session_state.inscricao_salva}.pdf",
            mime="application/pdf"
        )
    
    with col_d2:
        st.download_button(
            label="⬇️ Baixar Guia ITBI",
            data=st.session_state.arquivos_gerados['itbi'],
            file_name=f"ITBI_{st.session_state.inscricao_salva}.pdf",
            mime="application/pdf"
        )
