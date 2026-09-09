import streamlit as st

st.set_page_config(page_title="Emissor Atualizado", page_icon="⚠️")

# Espaçamento para centralizar
st.write("")
st.write("")

# Caixa de aviso destacada
st.warning("### ⚠️ Sistema Atualizado e Migrado!")
st.markdown(
    """
    O **Emissor de ITBI e CND** mudou de endereço para um servidor mais rápido e estável. 
    
    Por favor, atualize seus favoritos e acesse o novo sistema clicando no link abaixo:
    """
)

# Cria um botão/link gigante e chamativo
# SUBSTITUA O LINK ABAIXO PELO SEU ENDEREÇO REAL DO RENDER
link_novo = "https://itbigba.onrender.com/"

st.markdown(
    f"""
    <a href="{link_novo}" target="_blank" style="text-decoration: none;">
        <div style="background-color: #4CAF50; color: white; padding: 15px; text-align: center; border-radius: 8px; font-size: 18px; font-weight: bold;">
            👉 ACESSAR O NOVO EMISSOR AQUI 👈
        </div>
    </a>
    """, 
    unsafe_allow_html=True
)
