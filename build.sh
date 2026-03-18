#!/bin/bash
apt-get update -y
apt-get install -y tesseract-ocr tesseract-ocr-eng
pip install -r requirements.txt