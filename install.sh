#!/bin/bash

echo "🔧 Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-pyqt5 python3-pyqt5.qtwebengine

echo "📦 Installing Python packages..."
pip3 install --upgrade PyQt5 PyQtWebEngine

echo "📁 Setting up RenBrowser files..."
mkdir -p /opt/renbrowser
cp renbrowser.py /opt/renbrowser/

echo "🚀 Creating launcher..."
echo '#!/bin/bash' | sudo tee /usr/bin/renbrowser > /dev/null
echo 'python3 /opt/renbrowser/renbrowser.py' | sudo tee -a /usr/bin/renbrowser > /dev/null
sudo chmod +x /usr/bin/renbrowser

echo "🖼 Adding desktop entry..."
cp renbrowser.desktop /usr/share/applications/
sudo update-desktop-database

echo "✅ RenBrowser installed. You can launch it from the app menu or by typing 'renbrowser'."
