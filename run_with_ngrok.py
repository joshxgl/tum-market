from pyngrok import ngrok
from app import app

public_url = ngrok.connect(5000, bind_tls=True).public_url
print(f"NGROK_URL={public_url}")
with open("ngrok_url.txt", "w", encoding="utf-8") as f:
    f.write(public_url)

app.run(host="0.0.0.0", port=5000)
