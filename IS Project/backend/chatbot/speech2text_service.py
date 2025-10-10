import requests
import base64
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BAIDU_API_KEY")
SECRET_KEY = os.getenv("BAIDU_SECRET_KEY")

def get_access_token():
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={API_KEY}&client_secret={SECRET_KEY}"
    
    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    
    return response.json()["access_token"]

def recognize_speech(audio_bytes: bytes, fmt: str = "wav", rate: int = 16000) -> dict:
    """
    Call Baidu API
    :param audio_bytes
    :param fmt: file format (wav)
    :param rate: sampling rate (16000Hz)
    :return: JSON
    """
    token = get_access_token()
    speech_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    url = f"https://vop.baidu.com/server_api"
    headers = {"Content-Type": "application/json"}
    payload = {
        "format": fmt,
        "rate": rate,
        "channel": 1,
        "token": token,
        "cuid": "streamlit_demo_user",
        "len": len(audio_bytes),
        "speech": speech_base64,
        "dev_pid": 1737  # English
    }

    res = requests.post(url, headers=headers, data=json.dumps(payload))
    return res.json()
