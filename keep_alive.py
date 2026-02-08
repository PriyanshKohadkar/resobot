import os
from flask import Flask
from threading import Thread

app = Flask('')
port = int(os.environ.get('PORT')
@app.route('/')
def home():
    return "Hello. I am alive!"

def run():
  app.run(host='0.0.0.0',port=port)

def keep_alive():
    t = Thread(target=run)

    t.start()


