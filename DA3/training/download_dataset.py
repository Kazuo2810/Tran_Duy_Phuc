from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile
URL="https://archive.ics.uci.edu/ml/machine-learning-databases/00501/PRSA2017_Data_20130301-20170228.zip"
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/"data"/"raw";ZIP=RAW/"beijing_air_quality.zip"
def main():
 RAW.mkdir(parents=True,exist_ok=True)
 if not ZIP.exists():print("Downloading dataset...");urlretrieve(URL,ZIP)
 with ZipFile(ZIP) as z:z.extractall(RAW)
 print("Extracted to",RAW)
if __name__=="__main__":main()
