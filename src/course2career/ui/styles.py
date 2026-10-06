import streamlit as st


def apply_product_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background: #F6F8F7;
            font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
        }
        [data-testid="stSidebar"] {
            background: #E5EEE7;
            border-right: 1px solid #CCD7D0;
        }
        .block-container {
            max-width: 1180px;
            padding-top: 2.5rem;
            padding-bottom: 4rem;
        }
        h1, h2, h3 {
            color: #173F35;
            letter-spacing: -0.025em;
        }
        h1 {
            font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            font-weight: 600;
            line-height: 1.4;
            text-wrap: balance;
        }
        p, li, label {
            line-height: 1.65;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #CCD7D0;
            border-radius: 8px;
            padding: 1rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.72);
            border-color: #CCD7D0;
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
            border: 1px solid #CCD7D0;
            border-radius: 8px;
            overflow: hidden;
        }
        [data-testid="stAlert"] {
            border-radius: 6px;
        }
        .c2c-kicker { color: #53675E; font-size: 0.9rem; }
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p { color: #53675E; }
        .c2c-lead {
            color: #53675E;
            font-size: 1.08rem;
            line-height: 1.75;
            max-width: 46rem;
        }
        .c2c-rule {
            border-top: 1px solid #CCD7D0;
            margin: 2rem 0;
        }
        .c2c-home-path {
            display: grid;
            grid-template-columns: 1fr 56px 1fr 56px 1fr;
            align-items: center;
            gap: 18px;
            padding: 36px 0;
            margin: 14px 0 26px;
            border-top: 1px solid #CCD7D0;
            border-bottom: 1px solid #CCD7D0;
        }
        .c2c-home-path strong { color: #173F35; font-size: 1.35rem; }
        .c2c-home-path p { color: #53675E; font-size: 0.9rem; margin: 10px 0 0; }
        .c2c-home-path svg { width: 48px; height: 56px; }
        .c2c-home-path .c2c-confirm strong { color: #B7472B; }
        .c2c-home-evidence {
            padding: 24px 28px;
            background: #E5EEE7;
            border-radius: 6px;
            margin: 20px 0;
        }
        .c2c-home-evidence span { color: #B7472B; font-size: 0.8rem; }
        .c2c-home-evidence h3 { margin-top: 12px; }
        .c2c-home-evidence p { color: #53675E; }
        a:focus-visible, button:focus-visible {
            outline: 3px solid #B7472B;
            outline-offset: 3px;
        }
        @media (max-width: 700px) {
            .block-container { padding: 2rem 1.25rem 3rem; }
            .c2c-home-path { grid-template-columns: 1fr; gap: 12px; }
            .c2c-home-path svg { height: 30px; transform: rotate(90deg); }
            .c2c-home-evidence { padding: 20px; }
        }
        @media (prefers-reduced-motion: reduce) {
            .stButton > button:active,
            .stDownloadButton > button:active,
            [data-testid="stFormSubmitButton"] > button:active { transform: none; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
