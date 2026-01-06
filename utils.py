# utils.py
import streamlit as st
import socket
import qrcode
import io

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

def generate_qr(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()

def render_custom_css():
    st.markdown("""
    <style>
        [data-testid="stVerticalBlock"] h3 { min-height: 110px; display: flex; align-items: center; text-align: center; justify-content: center; font-size: 1.5rem !important; }
        .team-header-blue { color: #4da6ff; border-bottom: 2px solid #4da6ff; padding-bottom: 5px; text-align: center; }
        .team-header-orange { color: #ff9f43; border-bottom: 2px solid #ff9f43; padding-bottom: 5px; text-align: center; }
        .cs-box { border: 2px solid #00E500; background-color: #0e1117; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
        .cs-title { color: #00E500; font-weight: bold; font-size: 1.2em; margin-bottom: 10px; }
        .map-box-container { text-align: center; border: 1px solid #333; padding: 10px; border-radius: 8px; background-color: #1E1E1E; }
        .map-order { color: #FFD700; font-weight: bold; font-size: 0.9em; margin-bottom: 5px; }
        .map-name { color: white; font-weight: bold; font-size: 1.1em; }
        .turn-indicator {
            background-color: #262730; border: 1px solid #444; color: #FFD700;
            padding: 10px; border-radius: 8px; text-align: center; font-size: 1.2em; font-weight: bold; margin-bottom: 15px;
        }
        .admin-badge { color: #00E500; font-size: 0.8em; font-weight: bold; margin-left: 10px; }
    </style>
    """, unsafe_allow_html=True)
