#!/usr/bin/env jupyter

from flask import Flask, request, render_template

app = Flask(__name__)

@app.route('/')
def my_form():
    return render_template('input_forms.html')

@app.route('/', methods=['POST'])
def my_form_post():
    text = request.form['smile']
    processed_text = text.upper()
    return [processed_text]

@app.route('/upload-file', methods=['POST'])
def upload():
    if request.method == 'POST':
        # FileStorage object wrapper
        f = request.files.get('smiles_list')
        result = [line.decode("utf-8") for line in f]
        return result
