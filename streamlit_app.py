import streamlit as st
from playwright.sync_api import sync_playwright
import time
import pdfplumber
import re

# Configuração da página DEVE ser a primeira linha do Streamlit
st.set_page_config(page_title="Emissor ITBI/CND", page_icon="📄")

# ==========================================
# CÉREBRO DE EXTRAÇÃO DO PDF
# ==========================================
def extrair_dados_pdf(arquivo_pdf):
    texto_completo = ""
    try:
        with pdfplumber.open(arquivo_pdf) as pdf:
            for pagina in pdf.pages:
                # layout=True tenta respeitar as colunas do boleto
                texto = pagina.extract_text(layout=True)
                if texto:
                    texto_completo += texto + "\n"

        inscricao = ""
        
        # TÁTICA BLINDADA PARA A INSCRIÇÃO: 
        # Procura a palavra Inscr ou Imóvel, ignora qualquer sujeira/endereço e pega o primeiro número com 10 a 20 dígitos.
        match_insc = re.search(r'(?:Inscr|Inser|Im[oó]vel)[^\d]*?(\d{10,20})', texto_completo, re.IGNORECASE | re.DOTALL)
        if match_insc:
            inscricao = match_insc.group(1)
        else:
            # Plano B: Pega qualquer bloco numérico de 14 dígitos isolado no texto
            match_insc_fallback = re.search(r'(?<![\.\-\/])\b(\d{14})\b(?![\.\-\/])', texto_completo)
            if match_insc_fallback:
                inscricao = match_insc_fallback.group(1)
            
        cpfs = re.findall(r'CPF/CNPJ:\s*([\d\.\-\/]+)', texto_completo, re.IGNORECASE)
        
        cpf_prop = cpfs[0] if len(cpfs) > 0 else ""
        cpf_compr = cpfs[1] if len(cpfs) > 1 else ""
        
        return inscricao, cpf_prop, cpf_compr
    except Exception as e:
        return "", "", ""

# ==========================================
# INTERFACE DO USUÁRIO & ESTADO
# ==========================================
# Cria a memória ancorada na 'key' das caixas de texto
if 'insc_input' not in st.session_state:
    st.session_state.insc_input = ""
if 'prop_input' not in st.session_state:
    st.session_state.prop_input = ""
if 'compr_input' not in st.session_state:
    st.session_state.compr_input = ""
if 'ultimo_arquivo' not in st.session_state:
    st.session_state.ultimo_arquivo = ""

st.title("📄 Automação de Tributos - Elmar")
st.markdown("Faça o upload do Boleto de ITBI para preencher os dados automaticamente ou digite manualmente.")

# ==========================================
# ÁREA DE UPLOAD
# ==========================================
arquivo_up = st.file_uploader("Arraste o Boleto de ITBI aqui (PDF)", type=["pdf"])

if arquivo_up is not None:
    # Impede que ele fique extraindo infinitamente o mesmo arquivo
    if st.session_state.ultimo_arquivo != arquivo_up.name:
        with st.spinner("Lendo documento..."):
            insc, prop, compr = extrair_dados_pdf(arquivo_up)
            
            # Injeta os valores na memória do aplicativo
            st.session_state.insc_input = insc
            st.session_state.prop_input = prop
            st.session_state.compr_input = compr
            st.session_state.ultimo_arquivo = arquivo_up.name
            
            # O SEGREDO: Força a interface a piscar e exibir os números lidos!
            st.rerun()

st.markdown("---")

# ==========================================
# FORMULÁRIO (AUTO-PREENCHIDO PELA MEMÓRIA)
# ==========================================
with st.form("dados_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        # A caixa agora obedece à 'key' que foi preenchida lá em cima
        inscricao = st.text_input("Inscrição Imobiliária", key="insc_input")
    with col2:     
        cpf_prop = st.text_input("CPF/CNPJ do Vendedor", key="prop_input")
    with col3:
        cpf_compr = st.text_input("CPF/CNPJ do Comprador", key="compr_input")
    
    submit_button = st.form_submit_button("Gerar Documentos")

# ==========================================
# MOTOR DE AUTOMAÇÃO (ROBÔ)
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
            page.goto("https://tributos.elmartecnologia.com.br/portal/?ecode=201082", wait_until="domcontentloaded", timeout=60000)
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
        st.warning("Por favor, preencha todos os campos (se não usar o PDF, digite os valores).")
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
                    
