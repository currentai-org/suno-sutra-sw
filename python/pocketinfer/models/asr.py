import base64
import io
import time
import librosa
import torch
import numpy as np
import onnxruntime as ort

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


SAMPLE_RATE = 16000

app = FastAPI(title="ASR API")


class ASRRequest(BaseModel):
    audio_base64: str
    language: str


VOCAB_HI = [
    '<unk>', 'ा', 'े', 'र', 'ी', 'न', 'ि', 'ल', 'क', '्', '▁', 'स', 'म', 'त',
    '▁स', 'ो', '▁द', '▁क', 'ट', 'ं', '▁अ', 'प', '▁ब', '▁प', 'व', 'ु', 'य',
    '▁है', '▁म', 'ह', '▁ज', '▁व', '▁आ', 'ग', 'द', '▁ह', 'ू', 'श', '्र',
    'ै', 'ब', '्य', '▁इ', 'ज', 'ड', '▁न', 'र्', '▁के', '▁ल', '▁में',
    'च', 'ए', 'ज़', '▁उ', 'ख', '▁र', '▁फ', 'ों', 'ॉ', 'भ', '▁ग',
    'ंग', 'ता', 'ने', '▁और', '▁का', 'ाइ', '्ट', '▁प्र', '▁को',
    '▁की', '▁कर', '▁हो', '▁से', '▁च', 'ध', '▁हैं', 'ई', '्s',
    '▁तो', '▁त', '▁थ', 'फ', 'थ', 'स्ट', '▁कि', 'न्ट', '▁भी'
]

VOCAB_TA = [
    '<unk>', 'ா', 'ி', 'ு', 'வ', 'க', '▁ப', 'ை', 'ன', 'ர', 'ன்', '்',
    '▁க', 'ம்', 'த', 'ே', 'ய', 'ல்', '▁அ', 'ர்', 'க்க', '▁வ',
    'ல', '▁ம', 'து', 'ட', 'ப்ப', 'ம', '▁த', 'ப', '▁', 'ச'
]


print("Loading ASR preprocessor...")
preprocessor = torch.jit.load(
    "hi-conformer_preprocess.pt",
    map_location="cpu"
).eval()

print("Loading ASR ONNX sessions...")
sessions = {
    "hi": ort.InferenceSession("hi-conformer.onnx"),
    "ta": ort.InferenceSession("ta-conformer.onnx"),
}

print("ASR Models loaded successfully.")


def decode_ctc(logits, vocab):

    blank = len(vocab)

    token_ids = np.argmax(logits, axis=-1)[0]

    tokens = []
    prev = blank

    for t in token_ids:
        t = int(t)

        if t != blank and t != prev and t < len(vocab):
            tokens.append(vocab[t])

        prev = t

    text = "".join(tokens).replace("▁", " ").strip()

    return text


@app.post("/asr")
def run_asr(req: ASRRequest):

    start_time = time.time()

    if req.language not in sessions:
        raise HTTPException(400, f"Unsupported language: {req.language}")

    vocab = VOCAB_HI if req.language == "hi" else VOCAB_TA


    try:
        audio_bytes = base64.b64decode(req.audio_base64)
    except Exception:
        raise HTTPException(400, "Invalid base64 audio")


    signal_np, _ = librosa.load(
        io.BytesIO(audio_bytes),
        sr=SAMPLE_RATE,
        mono=True
    )

    if signal_np.size == 0:
        raise HTTPException(400, "Empty audio")

    signal = torch.tensor(signal_np).unsqueeze(0)
    length = torch.tensor([signal.shape[1]])

    with torch.no_grad():
        feats, feat_len = preprocessor(signal, length)


    session = sessions[req.language]

    logits = session.run(
        [session.get_outputs()[0].name],
        {
            session.get_inputs()[0].name: feats.numpy(),
            session.get_inputs()[1].name: feat_len.numpy(),
        }
    )[0]

    text = decode_ctc(logits, vocab)

    return {
        "text": text,
        "language": req.language,
        "processing_time_sec": round(time.time() - start_time, 3)
    }
