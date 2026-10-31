# DSP-Final-Project
A web application that uses HTDemucs and Digital Signal Processing (DSP) to separate songs into six instrument stems, with individual volume controls, lyrics synchronization, and live microphone effects. In short, a web-app karaoke

# Karaokeifier

## How to Run

### Option 1: Google Colab (Recommended)

1. Open `Karaokeifier_Studio_Colab.ipynb` from this repository.
2. Click **Open in Colab** or upload the notebook to [Google Colab](https://colab.research.google.com/).
3. Go to **Runtime → Change runtime type** and select GPU (if available).
4. Run all notebook cells in order.
5. Wait for the application to start.
6. Open the generated public URL to access Karaokeifier Studio.

**Note:** Keep the Colab session running while using the application. The public URL is temporary.
### Option 2: Run Locally

**Requirements:** Python and FFmpeg.

1. Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/Karaokeifier-Studio.git
```

2. Open the project folder:

```bash
cd Karaokeifier-Studio
```

3. Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

4. Install the dependencies:

```bash
pip install -r requirements.txt
```

5. Make sure FFmpeg is installed and added to PATH.

6. Run the application:

```bash
python app.py
```

7. Open your browser and visit:

```text
http://localhost:8000
```
