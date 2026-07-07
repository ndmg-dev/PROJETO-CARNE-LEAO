import os
import urllib.request

def download_por_tessdata():
    tessdata_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tessdata')
    if not os.path.exists(tessdata_dir):
        os.makedirs(tessdata_dir)
        
    url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/por.traineddata"
    filepath = os.path.join(tessdata_dir, 'por.traineddata')
    
    if not os.path.exists(filepath):
        print(f"Downloading {url} to {filepath}...")
        try:
            urllib.request.urlretrieve(url, filepath)
            print("Download completed successfully.")
        except Exception as e:
            print(f"Error downloading: {e}")
    else:
        print("por.traineddata already exists.")

if __name__ == '__main__':
    download_por_tessdata()
