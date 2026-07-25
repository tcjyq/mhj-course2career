import streamlit as st


def apply_product_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background: #F7F6F3;
        }
        [data-testid="stSidebar"] {
            background: #FBFBFA;
            border-right: 1px solid #E4E3DE;
        }
        .block-container {
            max-width: 1180px;
            padding-top: 2.5rem;
            padding-bottom: 4rem;
        }
        h1, h2, h3 {
            color: #202522;
            letter-spacing: -0.025em;
        }
        h1 {
            font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
            line-height: 1.12;
        }
        p, li, label {
            line-height: 1.65;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #E4E3DE;
            border-radius: 8px;
            padding: 1rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.72);
            border-color: #E4E3DE;
            border-radius: 8px;
        }
        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
            border-radius: 6px;
            box-shadow: none;
            font-weight: 600;
        }
        .stButton > button:active,
        .stDownloadButton > button:active,
        [data-testid="stFormSubmitButton"] > button:active {
            transform: scale(0.99);
        }
        [data-testid="stDataFrame"] {
            border: 1px solid #E4E3DE;
            border-radius: 8px;
            overflow: hidden;
        }
        [data-testid="stAlert"] {
            border-radius: 6px;
        }
        .c2c-kicker {
            color: #65706A;
            font-family: "SFMono-Regular", Consolas, monospace;
            font-size: 0.75rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .c2c-lead {
            color: #59615D;
            font-size: 1.08rem;
            line-height: 1.75;
            max-width: 46rem;
        }
        .c2c-rule {
            border-top: 1px solid #DEDCD5;
            margin: 2rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
